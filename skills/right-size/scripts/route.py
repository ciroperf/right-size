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

Options:
  --harness claude-code|codex   default: claude-code
  --tier TIER                   skip the classifier and use this tier
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

- Code changes in a risk_floor area -> deep, whatever the size. Name the area in risk_area.
- Read-only questions, even about risk areas -> scout.
- A pattern you can state in one sentence, easy to verify -> mechanical.
- Ordinary features and fixes -> standard.
- No tests in the repo -> one tier higher (not for scout).
- Small but reasoning-heavy -> raise effort one step above the tier's default_effort instead of raising the tier.
- When unsure between two tiers, pick the lower one: the session escalates on failure.

`why` is one line with the two or three facts that drove the choice."""


def classify(task, facts, harness, hmap, tiers_text):
    prompt = (f"## tiers.yaml\n{tiers_text}\n\n## Repo facts\n{json.dumps(facts)}\n\n"
              f"## Task\n{task}\n")
    scout = hmap["tiers"]["scout"]
    if harness == "claude-code":
        cmd = ["claude", "-p", "--model", scout["model"], "--tools", "", "--system-prompt", SYSTEM,
               "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
               "--no-session-persistence", "--strict-mcp-config"]
        if scout.get("effort"):
            cmd += ["--effort", scout["effort"]]
        r = run(cmd, input=prompt, timeout=300)
        try:
            d = json.loads(r.stdout)
        except json.JSONDecodeError:
            sys.exit(f"right-size: classifier failed: {(r.stderr or r.stdout)[:400]}")
        out = d.get("structured_output") or json.loads(d.get("result") or "{}")
        return out, {"cost_usd": d.get("total_cost_usd"), "model_usage": d.get("modelUsage")}
    with tempfile.TemporaryDirectory() as tmp:
        schema, last = Path(tmp) / "schema.json", Path(tmp) / "last.json"
        schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
        cmd = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only",
               "-m", scout["model"], "-c", f"model_reasoning_effort={scout.get('effort') or 'low'}",
               "--output-schema", str(schema), "-o", str(last), "-"]
        r = run(cmd, input=SYSTEM + "\n\n" + prompt, timeout=300)
        if not last.exists():
            sys.exit(f"right-size: classifier failed: {(r.stderr or r.stdout)[-400:]}")
        return json.loads(last.read_text(encoding="utf-8")), {"cost_usd": None}


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


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("task")
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

    tiers = read_yaml(SKILL / "tiers.yaml")
    hmap = read_yaml(SKILL / "harnesses" / f"{args.harness}.yaml")
    facts = repo_facts()

    if args.tier:
        decision, classifier = {"tier": args.tier, "effort": hmap["tiers"][args.tier].get("effort"),
                                "risk_area": None, "why": "tier set by the user"}, None
    else:
        decision, classifier = classify(args.task, {k: v for k, v in facts.items() if k != "root"},
                                        args.harness, hmap, (SKILL / "tiers.yaml").read_text(encoding="utf-8"))
    tier, capped = cap(decision["tier"], facts["max_tier"])
    p = profile(tier, decision.get("effort"), hmap, tiers)
    top = facts["max_tier"] or "deep"

    def next_profile(cur, steps=1):
        i = min(TIERS.index(cur) + steps, TIERS.index(top))
        return None if i <= TIERS.index(cur) else profile(TIERS[i], None, hmap, tiers)

    why = decision["why"] + (f" (capped at max_tier={top})" if capped else "")
    nxt = next_profile(tier)
    sys_note = note(p, why, nxt, interactive=not args.headless)
    cmd = launch_cmd(args.harness, p, args.task, extra, sys_note, args.headless)

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

    runs, prompt = [], args.task
    if args.log:
        args.log.mkdir(parents=True, exist_ok=True)
    for attempt in range(args.max_escalations + 1):
        log = args.log / f"run-{attempt}-{p['tier']}.jsonl" if args.log else None
        text, sid, result = headless_run(args.harness, cmd, prompt, log)
        runs.append({"profile": p, "session_id": sid, "result": result})
        m = MARKER.search(text or "")
        if not m or attempt == args.max_escalations or not sid:
            break
        steps = 2 if m.group(1).lower() == "reasoning" else 1
        up = next_profile(p["tier"], steps)
        if up is None:
            sys.stderr.write(f"right-size: escalation requested ({m.group(2).strip()}) but {p['tier']} is the "
                             f"ceiling; rerun with --tier or raise max_tier to go further\n")
            break
        sys.stderr.write(f"right-size: escalate · {p['tier']} → {up['tier']} ({up['model']}, effort "
                         f"{up['effort'] or 'default'}) · {m.group(2).strip()}\n")
        p = up
        why = f"escalated after: {m.group(2).strip()}"
        sys_note = note(p, why, next_profile(p["tier"]), interactive=False)
        prompt = (f"You are now on the {p['tier']} profile. The previous attempt asked to escalate: "
                  f"{m.group(2).strip()}. Continue the task from where it stopped.")
        cmd = launch_cmd(args.harness, p, prompt, extra, sys_note, True, resume=sid)

    if args.json:
        print(json.dumps({"decision": decision, "facts": facts, "classifier": classifier, "runs": runs}, indent=2))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
