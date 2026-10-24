#!/usr/bin/env python3
"""right-size router: pick the model and effort for a whole session before it starts.

Inside a running session, right-size can only save by delegating: the main
session's model is fixed once it starts. The router moves the decision in
front of the session and launches the harness on a tier's model and effort.

By default it climbs a ladder: headless with tests, it starts on the cheapest
writing tier (mechanical) and checks every attempt, escalating one tier when a
check fails; otherwise it starts on standard. With --classify, a cheap
classifier call (the harness's scout model) sizes the task with tiers.yaml
instead and picks the starting tier.

Usage:
  python route.py [options] "task"            # interactive session
  python route.py --print [options] "task"    # headless, with automatic escalation
  python route.py --dry-run "task"            # show the decision and the command only
  python route.py --file issue.md             # read the task from a file ("-" reads stdin)
  python route.py --print --split "task"      # independent parts run as separate sessions

Options:
  --harness claude-code|codex   default: claude-code
  --tier TIER                   start on this tier
  --classify                    let the classifier pick the starting tier (and spot risk areas,
                                which then get a deep-tier review)
  --split                       headless only, implies --classify: when the task is several
                                independent requests, run each as its own session on its own tier
  --file PATH                   read the task from PATH, or from stdin with "-"
  --max-escalations N           headless only, default 3 (mechanical up to deep at high effort)
  --verify-cmd CMD              headless only: shell command run after each attempt; a non-zero
                                exit escalates (e.g. the test suite, or the tests for changed files)
  --review auto|always|never    headless only: have a higher tier review the diff after each
                                attempt; auto (default) reviews risk areas and mechanical sessions
  --no-checks                   headless only: escalate only when the session asks to
  --log DIR                     headless only: write each run's raw event stream there
  --json                        headless only: print a JSON summary instead of the reply
  -- ARGS...                    passed through to the harness CLI

Headless escalation doesn't rely on the model alone: measured on the benchmark,
models at every tier stop with a wrong answer and believe it is right. After
each attempt the router checks the work (no file changed, the verify command
fails, or a review rejects the diff; the reviewer may run throwaway probes)
and escalates one tier with the reason. A step that only raises effort resumes
the session; a step to a bigger model starts a fresh session with a brief (task,
current diff, reason), because resuming would re-read the whole conversation
uncached on the bigger model.

Standard library only, so it runs wherever the skill is installed.
"""

import argparse
import json
import os
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
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return float(v) if re.fullmatch(r"-?\d+\.\d+", v) else v


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


def detect_verify_cmd(root):
    """The project's test command from its build files, or None. Returns (cmd, source)."""
    root = Path(root)
    pkg = root / "package.json"
    if pkg.exists():
        try:
            script = (json.loads(pkg.read_text(encoding="utf-8")).get("scripts") or {}).get("test", "")
        except (json.JSONDecodeError, AttributeError):
            script = ""
        # npm init's placeholder fails on purpose: it is not a test suite.
        if script and "no test specified" not in script:
            pm = next((m for f, m in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lock", "bun"),
                                      ("bun.lockb", "bun")) if (root / f).exists()), "npm")
            return f"{pm} run test", "package.json"
    if (root / "Cargo.toml").exists():
        return "cargo test", "Cargo.toml"
    if (root / "go.mod").exists():
        return "go test ./...", "go.mod"
    py = root / "pyproject.toml"
    if (root / "pytest.ini").exists() or (py.exists() and "[tool.pytest" in py.read_text(encoding="utf-8")):
        return "python -m pytest -q", "pytest config"
    mk = root / "Makefile"
    if mk.exists() and re.search(r"^test:", mk.read_text(encoding="utf-8", errors="replace"), re.M):
        return "make test", "Makefile"
    return None, None


# --- classifier -------------------------------------------------------------

_DECISION = {
    "tier": {"enum": TIERS},
    "effort": {"enum": EFFORTS[:3]},
    "risk_area": {"type": ["string", "null"]},
    "why": {"type": "string"},
}

SCHEMA = {
    "type": "object",
    "properties": {
        **_DECISION,
        "shared": {"type": "string"},
        "parts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "text": {"type": "string"}, **_DECISION},
                "required": ["title", "text", "tier", "effort", "risk_area", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["tier", "effort", "risk_area", "why", "shared", "parts"],
    "additionalProperties": False,
}

SYSTEM = """You size coding tasks for the right-size router. Pick the tier whose
model will run the WHOLE session that does the task, and its reasoning effort.
Use the tier definitions, risk floor and adjustments below. Do not explore:
decide from the task text and the repo facts only.

There is no inline tier and no delegation here: the routed session does the
work itself. Ignore `inline`, `delegate` and the delegation rules, and treat
each tier as the profile of the model that runs the session.

- Size by the structure of the change, not by its domain: how many places must
  change together and how many existing behaviors must keep working. A small,
  local fix in a security module is still a small, local fix.
- Code changes in a risk_floor area: name the area in risk_area and size the tier
  as for any other task. The router has the diff reviewed on the deep tier.
  A design change in that area (a new auth flow, a migration, a crypto scheme)
  -> deep. Only when the repo has no tests (test_files is 0) does any change in
  a risk area start at deep.
- Read-only questions, even about risk areas -> scout.
- A pattern you can state in one sentence, easy to verify -> mechanical.
- A bug fix with a clear reproduction in a repo with tests -> mechanical: the session
  is checked and escalates when a check fails.
- Features, and fixes that need design decisions -> standard.
- Changes that thread through several modules, or must keep many existing
  behaviors intact -> deep.
- No tests in the repo -> one tier higher (not for scout).
- Small but reasoning-heavy -> raise effort one step above the tier's default_effort instead of raising the tier.
- Risk alone is not a reason to raise effort or tier: the review covers it.
- When unsure between two tiers, pick the lower one: the work is checked and escalates on failure.

`why` is one line with the two or three facts that drove the choice.

The top-level tier is for the whole task done in one session. Also fill
`parts`, but ONLY when the task is several independent requests (separate
bugs, tickets or features) that touch different code and don't depend on
each other's results. Then give one entry per request: a short `title`, its
`text` copied verbatim from the task, and its own tier, effort, risk_area and
why. Put instructions that apply to every part (how to run tests, "do not
commit") in `shared`, verbatim. A single request, or steps of one change,
get `parts: []` and `shared: ""`."""


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
    out["shared"] = out.get("shared") or ""
    parts = out.get("parts") or []
    # A split is all or nothing: one malformed part means run the task whole.
    ok = all(isinstance(x, dict) and x.get("tier") in TIERS and str(x.get("text") or "").strip() for x in parts)
    out["parts"] = parts if ok and len(parts) >= 2 else []
    return out


# --- checks ---------------------------------------------------------------
# Run after each headless attempt that didn't ask to escalate. A failed check
# escalates like a verifiable failure: one tier up, with the reason.

def snapshot(root):
    """A tree id for the working tree, untracked files included, or None outside git.

    Uses a throwaway index, so the user's index and working tree are untouched.
    It writes git objects for changed files; `git gc` cleans them up.
    """
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        if run(["git", "read-tree", "HEAD"], cwd=root, env=env).returncode:
            return None
        run(["git", "add", "-A"], cwd=root, env=env)
        tree = run(["git", "write-tree"], cwd=root, env=env)
    return tree.stdout.strip() if tree.returncode == 0 else None


def wants_review(mode, p, risk_area, escalated=False):
    if mode == "always":
        return True
    if mode == "never":
        return False
    # Risk areas get a second pair of eyes instead of a bigger model from the start,
    # and the cheapest tier's work is reviewed because it is the one most often wrong.
    # So is any attempt after a failed check: the task already proved harder than its
    # first tier. On bench (2026-10-24) a Sonnet attempt after a Haiku failure passed the
    # tests unreviewed and failed the PR's tests, where Opus solved it.
    return bool(risk_area) or escalated or TIERS.index(p["tier"]) < TIERS.index("standard")


def reviewer_profile(p, risk_area, top, hmap, tiers):
    """deep for risk areas, otherwise one tier above the session, at least standard."""
    want = "deep" if risk_area else TIERS[max(TIERS.index(p["tier"]) + 1, TIERS.index("standard"))]
    return profile(cap(want, top)[0], None, hmap, tiers)


REVIEW_SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"enum": ["pass", "fail"]}, "reason": {"type": "string"}},
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}

REVIEW_SYSTEM = """You review a change another model made for a coding task. You get
the task and the diff; you may read files in the repo to check the change in context.
Reading is not always enough: the existing tests passed, so a defect that remains is
one they don't cover. When you doubt that a requirement holds at runtime, write a
small throwaway test for it and run it{run_hint}. The working tree is
restored after your review, so don't clean up, and don't fix anything: report.
Answer fail only for a concrete defect you can point to: a requirement of the task
that the diff doesn't meet, or existing behavior the diff breaks. Name the file and
the requirement or behavior in `reason`, in one or two sentences the next attempt
can act on. Style, naming, missing tests and leftover scratch files are not defects.
Otherwise answer pass."""

MAX_DIFF_CHARS = 100_000


def probe_runner(verify_cmd):
    """The test-runner part of the verify command, e.g. `npx vitest` from `npx vitest --run --changed`.

    The reviewer may run only this, on a probe test it writes: enough to check behavior,
    without handing a headless session arbitrary commands.
    """
    words = []
    for w in (verify_cmd or "").split():
        if words and words[-1] == "-m":
            words.append(w)
            continue
        if (w.startswith("-") and w != "-m") or w.startswith(".") or "/" in w or "=" in w:
            break
        words.append(w)
    if words and words[-1] == "-m":
        words.pop()
    return " ".join(words) or None


def with_allowed(extra, rules):
    """The harness args with `rules` added to their --allowedTools list, or a new list."""
    extra = list(extra)
    for flag in ("--allowedTools", "--allowed-tools"):
        if flag in extra:
            i = extra.index(flag) + 1
            return extra[:i] + rules + extra[i:]
    return extra + ["--allowedTools", *rules]


def restore(root, tree, now):
    """Put the working tree back to snapshot `tree` after a review that ran probes.

    Only paths that differ between the two snapshots are touched: files the
    review changed or deleted are checked out again, files it added are removed.
    """
    if not tree or not now or tree == now:
        return
    changed = run(["git", "diff", "--name-only", "--no-renames", "--diff-filter=MD", tree, now],
                  cwd=root).stdout.splitlines()
    added = run(["git", "diff", "--name-only", "--no-renames", "--diff-filter=A", tree, now],
                cwd=root).stdout.splitlines()
    if changed:
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
            run(["git", "read-tree", tree], cwd=root, env=env)
            run(["git", "checkout-index", "-f", "--", *changed], cwd=root, env=env)
    for f in added:
        (Path(root) / f).unlink(missing_ok=True)


def review(task, diff, rp, harness, root, verify_cmd=None, extra=()):
    """One review call that may run throwaway probes; the working tree is restored afterwards.

    Returns (ok, reason, info); ok is None when the review couldn't run.
    `extra` is the harness arguments the sessions get, so the review has the same permissions.
    """
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n[diff truncated]"
    runner = probe_runner(verify_cmd)
    # On bench (2026-10-24) a reviewer wrote its probe with a shell heredoc, which the
    # allowlist denies; naming the Write tool avoids the wasted turn.
    system = REVIEW_SYSTEM.format(run_hint=f": create the file with the Write tool, then run `{runner} <your test file>`,"
                                  f" the only command you can run" if runner else "")
    prompt = f"## Task\n{task}\n\n## Diff\n```diff\n{diff}\n```\n"
    before = snapshot(root)
    try:
        if harness == "claude-code":
            # Headless sessions deny shell commands that aren't allowed explicitly: without
            # these rules every probe was denied on bench v1 (2026-10-21).
            shells = ["Bash", "PowerShell"] if os.name == "nt" else ["Bash"]
            rules = ["Write", *(f"{sh}({runner}{suffix})" for sh in shells for suffix in ("", " *"))] if runner else []
            cmd = ["claude", "-p", "--model", rp["model"], "--tools", ",".join(["Read", "Grep", "Glob", "Write", *shells]),
                   "--system-prompt", system, "--output-format", "json",
                   "--json-schema", json.dumps(REVIEW_SCHEMA), "--no-session-persistence",
                   "--strict-mcp-config", "--disable-slash-commands", "--max-budget-usd", "1"]
            if rp["effort"]:
                cmd += ["--effort", rp["effort"]]
            r = run(cmd + (with_allowed(extra, rules) if rules else list(extra)), input=prompt, cwd=root, timeout=900)
            d = json.loads(r.stdout)
            out = d.get("structured_output") or json.loads(d.get("result") or "{}")
            info = {"cost_usd": d.get("total_cost_usd"), "model_usage": d.get("modelUsage"),
                    "denied": [x.get("tool_input") for x in d.get("permission_denials") or []]}
        else:
            with tempfile.TemporaryDirectory() as tmp:
                schema, last = Path(tmp) / "schema.json", Path(tmp) / "last.json"
                schema.write_text(json.dumps(REVIEW_SCHEMA), encoding="utf-8")
                cmd = ["codex", "exec", "--ephemeral", "-s", "workspace-write", "-m", rp["model"],
                       *(["-c", f"model_reasoning_effort={rp['effort']}"] if rp["effort"] else []),
                       "--output-schema", str(schema), "-o", str(last), "-"]
                run(cmd, input=system + "\n\n" + prompt, cwd=root, timeout=900)
                out = json.loads(last.read_text(encoding="utf-8"))
            info = {"cost_usd": None}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, TypeError, AttributeError) as e:
        return None, f"review unavailable ({type(e).__name__})", {"cost_usd": None}
    finally:
        after = snapshot(root)
        restore(root, before, after)
    info["probed"] = bool(before and after and before != after)  # the review wrote a file
    if not isinstance(out, dict) or out.get("verdict") not in ("pass", "fail"):
        return None, "review unavailable (unexpected answer)", info
    return out["verdict"] == "pass", str(out.get("reason") or ""), info


def tail(text, n=40):
    return "\n".join((text or "").strip().splitlines()[-n:])


def check_attempt(ck, p, hmap, tiers):
    """External checks on an attempt. Returns (failure reason or None, records)."""
    records = []
    if p["tier"] == "scout" or not ck:
        return None, records
    end = snapshot(ck["root"])
    if ck["start"] and end == ck["start"]:
        records.append({"kind": "diff", "ok": False})
        return "the attempt changed no files", records
    if ck["verify_cmd"]:
        try:
            # CI=1 and no stdin: runners like vitest and jest otherwise start in watch mode
            # from a terminal (a detected `npm run test` is often plain `vitest`) and never exit.
            r = subprocess.run(ck["verify_cmd"], shell=True, cwd=ck["root"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=1200,
                               stdin=subprocess.DEVNULL, env={**os.environ, "CI": "1"})
            ok, out = r.returncode == 0, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            ok, out = False, "timed out after 1200s"
        records.append({"kind": "verify", "ok": ok})
        if not ok:
            return f"`{ck['verify_cmd']}` failed:\n{tail(out)}", records
    if wants_review(ck["review"], p, ck["risk_area"], ck.get("escalated")) and ck["start"] and end:
        diff = run(["git", "diff", ck["start"], end], cwd=ck["root"]).stdout
        rp = reviewer_profile(p, ck["risk_area"], ck["top"], hmap, tiers)
        ok, reason, info = review(ck["task"], diff, rp, ck["harness"], ck["root"], ck["verify_cmd"],
                                  ck.get("extra", ()))
        records.append({"kind": "review", "ok": ok, "reason": reason, "profile": rp, **info})
        if ok is False:
            return f"a {rp['tier']}-tier review rejected the change: {reason}", records
    return None, records


def part_prompt(part, shared, n, total):
    """The prompt for one part of a split task: its own text plus the shared instructions."""
    head = (f"This is part {n} of {total} of a larger request. The other parts are handled in "
            f"separate sessions: do only this one.")
    return "\n\n".join(x for x in (head, part["text"].strip(), shared.strip()) if x)


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


def next_profile(p, steps, top, hmap, tiers):
    """The escalation target from profile `p`, or None when there is nowhere left to go.

    Steps up `steps` tiers within `top`. Already at `top`, it raises effort one
    step instead, up to high (tiers.yaml escalation.at_top_tier).
    """
    i = min(TIERS.index(p["tier"]) + steps, TIERS.index(top))
    if i > TIERS.index(p["tier"]):
        return profile(TIERS[i], None, hmap, tiers)
    if p["effort"] in EFFORTS and EFFORTS.index(p["effort"]) < EFFORTS.index("high"):
        return {**p, "effort": EFFORTS[EFFORTS.index(p["effort"]) + 1]}
    return None


def cap(tier, max_tier):
    if max_tier and TIERS.index(tier) > TIERS.index(max_tier):
        return max_tier, True
    return tier, False


def note(p, why, nxt, interactive, checks=None):
    lines = [f"right-size router: this session runs on the {p['tier']} profile "
             f"({p['model']}, effort {p['effort'] or 'default'}), chosen because: {why}.",
             "Work inline. Spawn subagents only if the task clearly splits into independent parts.",
             # v1 pilot: fixes that broke existing tests were reported as done, so nothing escalated.
             "Before calling the task done, run the existing tests of every module you changed, not only "
             "tests you wrote: an existing test that turns red is a failed check."]
    if checks and not interactive and p["tier"] != "scout":
        what = ["it fails if no file changed"]
        if checks["verify_cmd"]:
            what.append(f"it runs `{checks['verify_cmd']}`, so run it yourself before you stop")
        if wants_review(checks["review"], p, checks["risk_area"], checks.get("escalated")):
            what.append("a higher tier reviews the diff against the task")
        lines.append("When you stop, the router checks the work: " + "; ".join(what) + ". "
                     "Delete scratch or debug files you created before you stop.")
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
                     "A fix you could not get a check to pass on counts as failed: escalate with verifiable. "
                     "Nobody answers questions in this session: instead of asking, act on the most likely "
                     "reading, or escalate with reasoning if you can't tell what is wanted. "
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
    reviews = sum(c.get("cost_usd") or 0 for r in runs for c in r.get("checks") or [])
    total = router + reviews + sum(r.get("cost_usd") or 0 for r in runs)
    return (f"right-size: done · {' → '.join(parts)} · router ${router:.4f}"
            + (f" · reviews ${reviews:.2f}" if reviews else "") + f" · total ${total:.2f}")


MAX_BRIEF_DIFF_CHARS = 30_000


def escalation_brief(task, prev, reason, diff):
    """The prompt for a fresh session on a bigger model, in place of resuming the old one.

    Resuming makes the bigger model re-read the whole previous conversation
    without cache, which measured as most of an escalation's cost. The brief
    carries what matters: the task, what the working tree holds now, and why
    the last attempt was not accepted.
    """
    if diff is None:
        state = "## Current changes\nThe working tree holds the previous attempt's changes: run `git diff` to see them."
    elif not diff.strip():
        state = "## Current changes\nThe working tree has no changes yet."
    else:
        if len(diff) > MAX_BRIEF_DIFF_CHARS:
            diff = diff[:MAX_BRIEF_DIFF_CHARS] + "\n[diff truncated: run `git diff` for the rest]"
        state = ("## Current changes\nThe working tree already holds these changes from the previous attempt:\n"
                 f"```diff\n{diff}\n```")
    return (f"## Task\n{task}\n\n## Previous attempt\nAn attempt on the {prev['tier']} tier ({prev['model']}) "
            f"was not accepted: {reason}\n\nStart from the current changes: keep what is right, fix what the "
            f"check found, and finish the task. Read the code you need, and don't trust the previous attempt's "
            f"conclusions.\n\n{state}\n")


def run_headless(harness, p, prompt, extra, why, top, hmap, tiers, max_escalations, log_dir, label="",
                 checks=None):
    """One routed headless session, with escalation. Returns (runs, final text).

    `checks` (from make_checks) enables the external checks; None leaves
    escalation to the session's own marker. An escalation that keeps the model
    (effort only) resumes the session, since effort changes keep the prompt
    cache; one that changes the model starts a fresh session with a brief.
    """
    task = prompt
    root = checks["root"] if checks else None
    start = snapshot(root) if root else None
    if checks:
        checks = {**checks, "task": task, "start": start, "extra": extra}
    nxt = next_profile(p, 1, top, hmap, tiers)
    cmd = launch_cmd(harness, p, prompt, extra, note(p, why, nxt, False, checks), True)
    runs, text, resumed = [], "", False
    for attempt in range(max_escalations + 1):
        log = log_dir / f"{label}run-{attempt}-{p['tier']}.jsonl" if log_dir else None
        text, sid, result = headless_run(harness, cmd, prompt, log)
        cost, usage = own_usage(result, runs[-1]["result"] if runs and resumed else None)
        run_rec = {"profile": p, "session_id": sid, "cost_usd": cost, "model_usage": usage, "result": result,
                   "checks": [], "resumed": resumed}
        runs.append(run_rec)
        m = MARKER.search(text or "")
        if m:
            reason, steps, kind = m.group(2).strip(), 2 if m.group(1).lower() == "reasoning" else 1, "asked"
        else:
            reason, run_rec["checks"] = check_attempt(checks, p, hmap, tiers)
            steps, kind = 1, "check"
            if reason is None:
                break
        short = reason.splitlines()[0][:200]
        if attempt == max_escalations:
            sys.stderr.write(f"right-size: escalation needed ({short}) but the escalation limit was reached\n")
            break
        up = next_profile(p, steps, top, hmap, tiers)
        if up is None:
            sys.stderr.write(f"right-size: escalation needed ({short}) but {p['tier']} is the ceiling; "
                             f"rerun with --tier or raise max_tier to go further\n")
            break
        sys.stderr.write(f"right-size: escalate · {label}{p['tier']} → {up['tier']} ({up['model']}, effort "
                         f"{up['effort'] or 'default'}) · {short}\n")
        prev, p = p, up
        if checks:
            checks = {**checks, "escalated": True}
        sys_note = note(p, f"escalated after: {short}", next_profile(p, 1, top, hmap, tiers), False, checks)
        why_not = (f"it asked to escalate: {reason}" if kind == "asked"
                   else f"a check failed: {reason[:3000]}")
        resumed = p["model"] == prev["model"] and bool(sid)
        if resumed:
            if kind == "asked":
                prompt = (f"You are now on the {p['tier']} profile. The previous attempt asked to escalate: "
                          f"{reason}. Continue the task from where it stopped.")
            else:
                prompt = (f"You are now on the {p['tier']} profile. A check after the previous attempt failed: "
                          f"{reason[:3000]}\n\nFix this and finish the task.")
            cmd = launch_cmd(harness, p, prompt, extra, sys_note, True, resume=sid)
        else:
            diff = run(["git", "diff", start, snapshot(root)], cwd=root).stdout if start else None
            prompt = escalation_brief(task, prev, why_not, diff)
            cmd = launch_cmd(harness, p, prompt, extra, sys_note, True)
    return runs, text


# Without --classify the router doesn't guess a starting tier: it starts cheap and lets
# the checks escalate. Measured on bench v1 (2026-10-21): starting on mechanical with
# checks solved as many tasks as the classifier's pick at about a third of the cost.
LADDER_WHY = {
    "mechanical": "ladder: start on the cheapest writing tier, checks escalate on failure",
    "standard": "ladder: no test command checks the attempts here (interactive, --no-checks, "
                "no tests or no --verify-cmd), so start on standard",
}


def ladder_start(checked, facts, verify_cmd):
    """mechanical when every attempt is checked by running tests, standard otherwise.

    A review alone is not enough: on bench v1 a defect passed a review that read the diff.
    """
    return "mechanical" if checked and facts["test_files"] and verify_cmd else "standard"


def make_checks(args, facts, risk_area, top, harness):
    if args.no_checks:
        return None
    return {"root": facts["root"], "verify_cmd": args.verify_cmd, "review": args.review,
            "risk_area": risk_area, "top": top, "harness": harness}


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("task", nargs="?")
    ap.add_argument("--file")
    ap.add_argument("--harness", default="claude-code", choices=["claude-code", "codex"])
    ap.add_argument("--tier", choices=TIERS)
    ap.add_argument("--print", dest="headless", action="store_true")
    ap.add_argument("--split", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--classify", action="store_true")
    ap.add_argument("--max-escalations", type=int, default=3)
    ap.add_argument("--verify-cmd")
    ap.add_argument("--review", choices=["auto", "always", "never"], default="auto")
    ap.add_argument("--no-checks", action="store_true")
    ap.add_argument("--log", type=Path)
    ap.add_argument("--json", action="store_true")
    argv = sys.argv[1:]
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    args = ap.parse_args(argv[:argv.index("--")] if "--" in argv else argv)
    task = read_task(args)

    tiers = read_yaml(SKILL / "tiers.yaml")
    hmap = read_yaml(SKILL / "harnesses" / f"{args.harness}.yaml")
    facts = repo_facts()

    checked = args.headless and not args.no_checks
    if checked and args.verify_cmd is None and facts["test_files"]:
        args.verify_cmd, source = detect_verify_cmd(facts["root"])
        if args.verify_cmd:
            sys.stderr.write(f"right-size: checks run `{args.verify_cmd}` (from {source}); "
                             f"--verify-cmd changes it\n")
    classifier = None
    if args.tier:
        decision = {"tier": args.tier, "effort": None, "risk_area": None, "why": "tier set by the user",
                    "shared": "", "parts": []}
    elif not (args.classify or args.split):
        tier = ladder_start(checked, facts, args.verify_cmd)
        decision = {"tier": tier, "effort": None, "risk_area": None, "shared": "", "parts": [],
                    "why": LADDER_WHY[tier]}
    else:
        try:
            decision, classifier = classify(task, {k: v for k, v in facts.items() if k != "root"}, args.harness,
                                            hmap, (SKILL / "tiers.yaml").read_text(encoding="utf-8"))
        except ClassifierError as e:
            sys.stderr.write(f"right-size: classifier unavailable ({e}); using {FALLBACK_TIER}\n")
            decision = {"tier": FALLBACK_TIER, "effort": None, "risk_area": None,
                        "why": "classifier unavailable, router fallback", "shared": "", "parts": []}
    tier, capped = cap(decision["tier"], facts["max_tier"])
    p = profile(tier, decision.get("effort"), hmap, tiers)
    top = facts["max_tier"] or "deep"

    why = decision["why"] + (f" (capped at max_tier={top})" if capped else "")
    nxt = next_profile(p, 1, top, hmap, tiers)
    sys_note = note(p, why, nxt, interactive=not args.headless)
    cmd = launch_cmd(args.harness, p, task, extra, sys_note, args.headless)

    eff = p["effort"] or "default"
    block = [f"right-size: route · tier={tier} · model={p['model']} · effort={eff}", f"why: {why}"]
    if nxt:
        block.append(f"escalate if: a real attempt fails → {nxt['tier']} ({nxt['model']}, effort {nxt['effort'] or 'default'})")
    sys.stderr.write("\n".join(block) + "\n")

    split = args.split and decision["parts"]
    if args.split and not decision["parts"]:
        sys.stderr.write("right-size: no independent parts found; running the task as one session\n")
    if split:
        plan = []
        for n, part in enumerate(decision["parts"], 1):
            t, was_capped = cap(part["tier"], facts["max_tier"])
            pp = profile(t, part.get("effort"), hmap, tiers)
            plan.append((part, pp, part["why"] + (f" (capped at max_tier={top})" if was_capped else "")))
            sys.stderr.write(f"right-size: part {n}/{len(decision['parts'])} · {part['title']} · tier={t} · "
                             f"model={pp['model']} · effort={pp['effort'] or 'default'}\n")
        if not args.headless:
            sys.stderr.write("right-size: split runs only with --print; starting one session for the whole task\n")
            split = False

    if args.dry_run:
        print(json.dumps({"decision": decision, "profile": p, "facts": facts, "classifier": classifier,
                          "command": cmd}, indent=2))
        return 0
    if not args.headless:
        exe = shutil.which(cmd[0]) or cmd[0]
        return subprocess.call([exe, *cmd[1:]])

    if args.log:
        args.log.mkdir(parents=True, exist_ok=True)
    if split:
        # Parts run one after another in the same working tree; they were judged
        # independent, so no part waits on another's result.
        parts_out, texts = [], []
        for n, (part, pp, part_why) in enumerate(plan, 1):
            runs, text = run_headless(args.harness, pp, part_prompt(part, decision["shared"], n, len(plan)),
                                      extra, part_why, top, hmap, tiers, args.max_escalations, args.log,
                                      label=f"part{n}-",
                                      checks=make_checks(args, facts, part.get("risk_area"), top, args.harness))
            parts_out.append({"title": part["title"], "runs": runs})
            texts.append(f"## Part {n}: {part['title']}\n\n{text}")
        runs = [r for x in parts_out for r in x["runs"]]
        text = "\n\n".join(texts)
        failed = any(not x["runs"][-1]["result"] or x["runs"][-1]["result"].get("is_error") for x in parts_out)
    else:
        runs, text = run_headless(args.harness, p, task, extra, why, top, hmap, tiers, args.max_escalations, args.log,
                                  checks=make_checks(args, facts, decision.get("risk_area"), top, args.harness))
        parts_out = None
        failed = not runs[-1]["result"] or runs[-1]["result"].get("is_error")

    if args.harness == "claude-code":
        sys.stderr.write(cost_line(classifier, runs) + "\n")
    if args.json:
        print(json.dumps({"decision": decision, "facts": facts, "classifier": classifier, "runs": runs,
                          "parts": parts_out}, indent=2))
    else:
        print(text)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
