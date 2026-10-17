#!/usr/bin/env python3
"""right-size router: pick the model and effort for a whole session before it starts.

Inside a running session, right-size can only save by delegating: the main
session's model is fixed once it starts. The router moves the decision in
front of the session. A cheap classifier call (the harness's scout model)
sizes the task with tiers.yaml, then the harness is launched on that tier's
model and effort.

Usage:
  python route.py [options] "task"            # interactive session
  python route.py --print [options] "task"    # headless, with automatic escalation
  python route.py --dry-run "task"            # show the decision and the command only
  python route.py --file issue.md             # read the task from a file ("-" reads stdin)

Options:
  --harness claude-code|codex   default: claude-code
  --tier TIER                   skip the classifier and use this tier
  --file PATH                   read the task from PATH, or from stdin with "-"
  --max-escalations N           headless only, default 2
  --log DIR                     headless only: write each run's raw event stream there
  --json                        headless only: print a JSON summary instead of the reply
  -- ARGS...                    passed through to the harness CLI

Standard library only, so it runs wherever the skill is installed.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TIERS = ["scout", "mechanical", "standard", "deep"]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]
MARKER = re.compile(r"RIGHT-SIZE-ESCALATE:\s*(verifiable|reasoning)\b[\s:—-]*(.*)", re.I)


# --- minimal YAML reader --------------------------------------------------
# Enough for tiers.yaml and harnesses/*.yaml: nested maps, scalar values and
# lists of scalars. Uses PyYAML instead when it's installed.

def _scalar(v):
    v = re.sub(r"\s+#.*$", "", v).strip()
    if v in ("", "null", "~"):
        return None
    if v in ("true", "false"):
        return v == "true"
    if v[0] in "\"'" and v[-1] == v[0]:
        return v[1:-1]
    return int(v) if re.fullmatch(r"-?\d+", v) else v


def read_yaml(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        pass
    lines = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    root = {}
    stack = [(-1, root)]
    for i, raw in enumerate(lines):
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            parent.append(_scalar(line[2:]))
            continue
        key, _, val = line.partition(":")
        val = re.sub(r"\s+#.*$", "", val).strip()
        if val:
            parent[key.strip()] = _scalar(val)
            continue
        # A container: the first child line decides whether it is a list or a map.
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        child = [] if nxt.startswith("- ") else {}
        parent[key.strip()] = child
        stack.append((indent, child))
    return root


# --- repo facts -------------------------------------------------------------

def run(cmd, **kw):
    exe = shutil.which(cmd[0]) or cmd[0]
    return subprocess.run([exe, *cmd[1:]], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def repo_facts():
    """Cheap facts the classifier can't see from the prompt: no model calls."""
    top = run(["git", "rev-parse", "--show-toplevel"])
    root = Path(top.stdout.strip()) if top.returncode == 0 else Path.cwd()
    files = run(["git", "ls-files"], cwd=root).stdout.splitlines() if top.returncode == 0 else []
    tests = [f for f in files if re.search(r"(^|/)(tests?|__tests__|spec)/|[._-](test|spec)\.\w+$|(^|/)test_\w+\.py$", f)]
    markers = [m for m in ("package.json", "pyproject.toml", "go.mod", "Cargo.toml", "pom.xml",
                           "build.gradle", "tsconfig.json", "mypy.ini") if (root / m).exists()]
    max_tier = None
    cfg = root / ".right-size.yaml"
    if cfg.exists():
        max_tier = (read_yaml(cfg) or {}).get("max_tier")
    return {
        "root": str(root),
        "tracked_files": len(files),
        "test_files": len(tests),
        "build_files": markers,
        "max_tier": max_tier if max_tier in TIERS else None,
    }


# --- classifier -------------------------------------------------------------

SCHEMA = {
    "type": "object",
    "properties": {
        "tier": {"enum": TIERS},
        "effort": {"enum": EFFORTS[:3]},
        "risk_area": {"type": ["string", "null"]},
        "why": {"type": "string"},
    },
    "required": ["tier", "effort", "risk_area", "why"],
    "additionalProperties": False,
}

SYSTEM = """You size coding tasks for the right-size router. Pick the tier whose
model will run the WHOLE session that does the task, and its reasoning effort.
Use the tier definitions, risk floor and adjustments below. Do not explore:
decide from the task text and the repo facts only.

There is no inline tier and no delegation here: the routed session does the
work itself. Ignore `inline`, `delegate` and the delegation rules, and treat
each tier as the profile of the model that runs the session.

- Code changes in a risk_floor area -> deep, whatever the size. Name the area in risk_area.
- Read-only questions, even about risk areas -> scout.
- A pattern you can state in one sentence, easy to verify -> mechanical.
- Ordinary features and fixes -> standard.
- No tests in the repo -> one tier higher (not for scout).
- Small but reasoning-heavy -> raise effort one step above the tier's default_effort instead of raising the tier.
- When unsure between two tiers, pick the lower one: the session escalates on failure.

`why` is one line with the two or three facts that drove the choice."""


class ClassifierError(Exception):
    pass


FALLBACK_TIER = "standard"  # middle of the ladder: safe for most fixes, cheap to escalate from


def classify(task, facts, harness, hmap, tiers_text):
    """One cheap call on the scout model. Raises ClassifierError when it can't decide."""
    prompt =(f"## tiers.yaml\n{tiers_text}\n\n## Repo facts\n{json.dumps(facts)}\n\n"
              f"## Task\n{task}\n")
    scout = hmap["tiers"]["scout"]
    if harness == "claude-code":
        # --tools "" also drops tool search, so MCP tool definitions would load
        # upfront (200k+ tokens with many connectors): keep --strict-mcp-config with it.
        cmd = ["claude", "-p", "--model", scout["model"], "--tools", "", "--system-prompt", SYSTEM,
               "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
               "--no-session-persistence", "--strict-mcp-config",
               # Skills only inflate the prompt here. Settings stay loaded: they may
               # carry the provider setup, such as Bedrock env vars.
               "--disable-slash-commands", "--max-budget-usd", "0.05"]
        if scout.get("effort"):
            cmd += ["--effort", scout["effort"]]
        r = run_checked(cmd, prompt)
        try:
            d = json.loads(r.stdout)
            out = d.get("structured_output") or json.loads(d.get("result") or "{}")
        except (json.JSONDecodeError, TypeError, AttributeError):
            raise ClassifierError(last_line(r))
        return validate(out), {"cost_usd": d.get("total_cost_usd"), "model_usage": d.get("modelUsage")}
    with tempfile.TemporaryDirectory() as tmp:
        schema, last = Path(tmp) / "schema.json", Path(tmp) / "last.json"
        schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
        cmd = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only",
               "-m", scout["model"], "-c", f"model_reasoning_effort={scout.get('effort') or 'low'}",
               "--output-schema", str(schema), "-o", str(last), "-"]
        r = run_checked(cmd, SYSTEM + "\n\n" + prompt)
        try:
            out = json.loads(last.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise ClassifierError(last_line(r))
        return validate(out), {"cost_usd": None}


def last_line(r):
    text = (r.stderr or "") + "\n" + (r.stdout or "")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-1][:200] if lines else f"exit code {r.returncode}, no output"


def run_checked(cmd, stdin):
    try:
        return run(cmd, input=stdin, timeout=300)
    except FileNotFoundError:
        raise ClassifierError(f"{cmd[0]} not found on PATH")
    except subprocess.TimeoutExpired:
        raise ClassifierError("timed out after 300s")


def validate(out):
    if not isinstance(out, dict) or out.get("tier") not in TIERS:
        raise ClassifierError(f"unexpected answer: {str(out)[:200]}")
    out.setdefault("why", "")
    out.setdefault("risk_area", None)
    return out


# --- decision ---------------------------------------------------------------

def profile(tier, effort, hmap, tiers):
    """Model and effort for a tier. Effort may go one step above the tier default, never more."""
    entry = hmap["tiers"][tier]
    base = entry.get("effort")
    if base and effort in EFFORTS and base in EFFORTS:
        effort = EFFORTS[min(max(EFFORTS.index(effort), EFFORTS.index(base)), EFFORTS.index(base) + 1)]
    else:
        effort = base
    return {"tier": tier, "model": entry["model"], "effort": effort}


def next_profile(cur, steps, top, hmap, tiers):
    """The profile `steps` tiers above `cur`, or None when `cur` is already at `top`."""
    i = min(TIERS.index(cur) + steps, TIERS.index(top))
    return None if i <= TIERS.index(cur) else profile(TIERS[i], None, hmap, tiers)


def cap(tier, max_tier):
    if max_tier and TIERS.index(tier) > TIERS.index(max_tier):
        return max_tier, True
    return tier, False


def note(p, why, nxt, interactive):
    lines = [f"right-size router: this session runs on the {p['tier']} profile "
             f"({p['model']}, effort {p['effort'] or 'default'}), chosen because: {why}.",
             "Work inline. Spawn subagents only if the task clearly splits into independent parts."]
    if nxt is None:
        lines.append("This is the highest tier the router may pick on its own; if it isn't enough, say so plainly.")
    elif interactive:
        lines.append(f"If after a real attempt the task needs more (tests stay red after a fix attempt, or the "
                     f"approach is wrong), stop and tell the user to switch with `/model {nxt['model']}`"
                     + (f" and `/effort {nxt['effort']}`" if nxt["effort"] else "") + ". Syntax or tooling "
                     "errors are not a reason: fix them and retry once.")
    else:
        lines.append("If after a real attempt the task needs more (tests stay red after a fix attempt, or the "
                     "approach is wrong), stop and end your reply with exactly one line: "
                     "`RIGHT-SIZE-ESCALATE: verifiable - <reason>` (a check fails) or "
                     "`RIGHT-SIZE-ESCALATE: reasoning - <reason>` (wrong approach or misread spec). "
                     "Syntax or tooling errors are not a reason: fix them and retry once.")
    return " ".join(lines)


def launch_cmd(harness, p, task, extra, sys_note, headless, resume=None):
    if harness == "claude-code":
        # The task goes first: a variadic flag in `extra` (e.g. --allowedTools) would swallow it.
        cmd = ["claude"] + (["-p"] if headless else [task]) + ["--model", p["model"]]
        if p["effort"]:
            cmd += ["--effort", p["effort"]]
        cmd += ["--append-system-prompt", sys_note]
        if resume:
            cmd += ["--resume", resume]
        if headless:
            cmd += ["--output-format", "stream-json", "--verbose"]
        return cmd + extra
    effort = ["-c", f"model_reasoning_effort={p['effort']}"] if p["effort"] else []
    instructions = ["-c", f"developer_instructions={json.dumps(sys_note)}"]
    if not headless:
        return ["codex", "-m", p["model"], *effort, *instructions, *extra, task]
    base = ["codex", "exec"] + (["resume", resume] if resume else [])
    return base + ["-c", f"model={json.dumps(p['model'])}", *effort, *instructions, "--json", *extra, "-"]


def headless_run(harness, cmd, task, log):
    """Run one headless session; return (final text, session id, result event)."""
    r = run(cmd, input=task)
    if log:
        log.write_text(r.stdout, encoding="utf-8")
    text, sid, result = "", None, None
    for line in r.stdout.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if harness == "claude-code":
            if e.get("type") == "system" and e.get("subtype") == "init":
                sid = e.get("session_id")
            elif e.get("type") == "result":
                result, text = e, e.get("result") or ""
        else:
            if e.get("type") == "thread.started":
                sid = e.get("thread_id")
            elif e.get("type") == "item.completed" and (e.get("item") or {}).get("type") == "agent_message":
                text = e["item"].get("text", "")
            elif e.get("type") == "turn.completed":
                result = e
    if result is None and not text:
        sys.stderr.write((r.stderr or r.stdout)[-2000:])
    return text, sid, result


def read_task(args):
    if args.file:
        return sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    if args.task == "-":
        return sys.stdin.read()
    if not args.task:
        sys.exit("right-size: give the task as an argument, or with --file")
    return args.task


def own_usage(result, prev):
    """This run's own cost and model usage.

    Claude Code reports a resumed session's totals cumulatively, so subtract
    what the previous run in the same session already reported.
    """
    result, prev = result or {}, prev or {}
    cost = (result.get("total_cost_usd") or 0) - (prev.get("total_cost_usd") or 0)
    usage = {}
    for model, u in (result.get("modelUsage") or {}).items():
        before = (prev.get("modelUsage") or {}).get(model, {})
        d = {k: v - before.get(k, 0) for k, v in u.items()
             if isinstance(v, (int, float)) and not isinstance(v, bool)}
        if any(d.values()):
            usage[model] = d
    return round(max(cost, 0), 6), usage


def cost_line(classifier, runs):
    parts = [f"{r['profile']['tier']} ({r['profile']['model']}) ${r.get('cost_usd') or 0:.2f}" for r in runs]
    router = (classifier or {}).get("cost_usd") or 0
    total = router + sum(r.get("cost_usd") or 0 for r in runs)
    return f"right-size: done · {' → '.join(parts)} · router ${router:.4f} · total ${total:.2f}"


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("task", nargs="?")
    ap.add_argument("--file")
    ap.add_argument("--harness", default="claude-code", choices=["claude-code", "codex"])
    ap.add_argument("--tier", choices=TIERS)
    ap.add_argument("--print", dest="headless", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-escalations", type=int, default=2)
    ap.add_argument("--log", type=Path)
    ap.add_argument("--json", action="store_true")
    argv = sys.argv[1:]
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    args = ap.parse_args(argv[:argv.index("--")] if "--" in argv else argv)
    task = read_task(args)

    tiers = read_yaml(SKILL / "tiers.yaml")
    hmap = read_yaml(SKILL / "harnesses" / f"{args.harness}.yaml")
    facts = repo_facts()

    classifier = None
    if args.tier:
        decision = {"tier": args.tier, "effort": None, "risk_area": None, "why": "tier set by the user"}
    else:
        try:
            decision, classifier = classify(task, {k: v for k, v in facts.items() if k != "root"}, args.harness,
                                            hmap, (SKILL / "tiers.yaml").read_text(encoding="utf-8"))
        except ClassifierError as e:
            sys.stderr.write(f"right-size: classifier unavailable ({e}); using {FALLBACK_TIER}\n")
            decision = {"tier": FALLBACK_TIER, "effort": None, "risk_area": None,
                        "why": "classifier unavailable, router fallback"}
    tier, capped = cap(decision["tier"], facts["max_tier"])
    p = profile(tier, decision.get("effort"), hmap, tiers)
    top = facts["max_tier"] or "deep"

    why = decision["why"] + (f" (capped at max_tier={top})" if capped else "")
    nxt = next_profile(tier, 1, top, hmap, tiers)
    sys_note = note(p, why, nxt, interactive=not args.headless)
    cmd = launch_cmd(args.harness, p, task, extra, sys_note, args.headless)

    eff = p["effort"] or "default"
    block = [f"right-size: route · tier={tier} · model={p['model']} · effort={eff}", f"why: {why}"]
    if nxt:
        block.append(f"escalate if: a real attempt fails → {nxt['tier']} ({nxt['model']}, effort {nxt['effort'] or 'default'})")
    sys.stderr.write("\n".join(block) + "\n")

    if args.dry_run:
        print(json.dumps({"decision": decision, "profile": p, "facts": facts, "classifier": classifier,
                          "command": cmd}, indent=2))
        return 0
    if not args.headless:
        exe = shutil.which(cmd[0]) or cmd[0]
        return subprocess.call([exe, *cmd[1:]])

    runs, prompt, text = [], task, ""
    if args.log:
        args.log.mkdir(parents=True, exist_ok=True)
    for attempt in range(args.max_escalations + 1):
        log = args.log / f"run-{attempt}-{p['tier']}.jsonl" if args.log else None
        text, sid, result = headless_run(args.harness, cmd, prompt, log)
        cost, usage = own_usage(result, runs[-1]["result"] if runs else None)
        runs.append({"profile": p, "session_id": sid, "cost_usd": cost, "model_usage": usage, "result": result})
        m = MARKER.search(text or "")
        if not m:
            break
        reason = m.group(2).strip()
        if attempt == args.max_escalations or not sid:
            sys.stderr.write(f"right-size: escalation requested ({reason}) but the escalation limit was reached\n")
            break
        up = next_profile(p["tier"], 2 if m.group(1).lower() == "reasoning" else 1, top, hmap, tiers)
        if up is None:
            sys.stderr.write(f"right-size: escalation requested ({reason}) but {p['tier']} is the ceiling; "
                             f"rerun with --tier or raise max_tier to go further\n")
            break
        sys.stderr.write(f"right-size: escalate · {p['tier']} → {up['tier']} ({up['model']}, effort "
                         f"{up['effort'] or 'default'}) · {reason}\n")
        p = up
        sys_note = note(p, f"escalated after: {reason}", next_profile(p["tier"], 1, top, hmap, tiers),
                        interactive=False)
        prompt = (f"You are now on the {p['tier']} profile. The previous attempt asked to escalate: "
                  f"{reason}. Continue the task from where it stopped.")
        cmd = launch_cmd(args.harness, p, prompt, extra, sys_note, True, resume=sid)

    if args.harness == "claude-code":
        sys.stderr.write(cost_line(classifier, runs) + "\n")
    if args.json:
        print(json.dumps({"decision": decision, "facts": facts, "classifier": classifier, "runs": runs}, indent=2))
    else:
        print(text)
    last = runs[-1]["result"]
    return 1 if not last or last.get("is_error") else 0


if __name__ == "__main__":
    sys.exit(main())
