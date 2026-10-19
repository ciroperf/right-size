"""right-size benchmark runner.

Usage:
  python bench/run.py validate [--tasks id,id]
  python bench/run.py run --out bench/results/<name> [--configs a,b] [--tasks id,id]
  python bench/run.py summarize bench/results/<name>

Each run checks out the commit before a real merged PR, gives the agent the
task prompt in headless Claude Code, then copies the PR's own test files in and
runs them. Token usage and list-price cost come from Claude Code's JSON result.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
WORK = BENCH / "work" / "hono"
RAW = BENCH / "raw"
BUN = ["npx", "-y", "bun@1.2.20"]
VITEST = ["npx", "vitest", "--run"]
TIMEOUT_S = 40 * 60

# The three setups compared. All run on the same main model; they differ in
# effort and in whether right-size is installed.
CONFIGS = {
    "default": {"model": "opus", "effort": None, "right_size": False},
    "max": {"model": "opus", "effort": "max", "right_size": False},
    # v1 references: Opus at high effort (a common manual setting) and always Sonnet.
    "opus-high": {"model": "opus", "effort": "high", "right_size": False},
    "sonnet": {"model": "sonnet", "effort": None, "right_size": False},
    "right-size": {"model": "opus", "effort": None, "right_size": True},
    # The router picks model and effort for the whole session before it starts
    # (skills/right-size/scripts/route.py), then escalates on request.
    "router": {"model": None, "effort": None, "right_size": False, "router": True},
    # Experiment: the router with its tier pinned, to see what a whole session on that tier costs.
    "router-standard": {"model": None, "effort": None, "right_size": False, "router": True, "tier": "standard"},
    # Cheapest first, escalate on failure: the router with its classifier skipped, starting on
    # mechanical (Haiku, low). Three escalations reach deep at high effort, like the router's ceiling.
    # Isolates what the classifier is worth: same escalation, no picked starting point.
    "ladder": {"model": None, "effort": None, "right_size": False, "router": True, "tier": "mechanical",
               "escalations": 3},
    # The router with --split: independent parts run as separate sessions on their own tiers.
    "router-split": {"model": None, "effort": None, "right_size": False, "router": True, "split": True},
    # Experiment, not a product setting: always delegate each independent part
    # to the right-size subagent for its tier, to measure what delegation costs.
    "delegate": {"model": "opus", "effort": None, "right_size": True, "nudge": "delegate"},
}

ROUTER = ROOT / "skills" / "right-size" / "scripts" / "route.py"

RIGHT_SIZE_NUDGE = "Before starting, size the task with the right-size skill and follow its decision."
DELEGATE_NUDGE = ("Size each independent part of the task with the right-size skill, then delegate every part "
                  "to the right-size-* subagent for its tier, in parallel where the parts are independent. "
                  "Do not fix any part yourself; review and verify the subagents' results.")

ALLOWED_TOOLS = [
    "Read", "Edit", "Write", "Glob", "Grep", "Agent", "Skill", "TodoWrite",
    "Bash(npx vitest *)", "PowerShell(npx vitest *)",
    "Bash(git diff *)", "Bash(git status *)", "Bash(git log *)",
]

PROMPT_SUFFIX = (
    "\n\nRun the relevant tests with: npx vitest --run <test file paths>\n"
    "Do not commit."
)


def sh(cmd, cwd=WORK, check=True, timeout=None, input=None):
    if isinstance(cmd, list):
        cmd = [shutil.which(cmd[0]) or cmd[0], *cmd[1:]]  # npx and claude are .cmd shims on Windows
    return subprocess.run(
        cmd, cwd=cwd, check=check, timeout=timeout, input=input,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        shell=isinstance(cmd, str),
    )


def load_tasks(only=None, task_set=None):
    spec = yaml.safe_load((BENCH / "tasks" / "hono.yaml").read_text(encoding="utf-8"))
    if task_set:
        only = ",".join(spec["sets"][task_set])
    by_id = {t["id"]: t for t in spec["tasks"]}
    for t in spec.get("batches", []):
        # A batch is several single-PR tasks in one prompt, on a commit where
        # every bug is still present. Each part is scored with its own PR's tests.
        t["parts"] = [by_id[i] for i in t["parts"]]
        t["pr"] = [x["pr"] for x in t["parts"]]
        t["prompt"] = (t["intro"].strip() + "\n\n" + "\n".join(
            f"{n}. {x['prompt'].strip()}\n" for n, x in enumerate(t["parts"], 1)))
    tasks = spec["tasks"] + spec.get("batches", [])
    if only:
        wanted = set(only.split(","))
        tasks = [t for t in tasks if t["id"] in wanted]
    return tasks


def units(task):
    """The single-PR tasks a task is scored on: itself, or a batch's parts."""
    return task.get("parts") or [task]


def base_rev(task):
    return task["base"] if task.get("parts") else f"{task['solution']}^"


def test_files(task):
    out = sh(["git", "diff", "--name-only", f"{task['solution']}^", task["solution"]]).stdout
    return [f for f in out.split() if f.startswith("src/") and (f.endswith(".test.ts") or f.endswith(".test.tsx"))]


def score(task):
    """Copy each unit's PR test files in and run them. Returns {unit id: (solved, log)}."""
    out = {}
    for u in units(task):
        files = test_files(u)
        sh(["git", "checkout", u["solution"], "--", *files])
        out[u["id"]] = run_tests(files)
    return out


_installed_lock = None


def checkout(rev):
    """Clean checkout of rev, reinstalling dependencies only if the lockfile changed."""
    global _installed_lock
    sh(["git", "checkout", "-f", "-q", rev])
    sh(["git", "clean", "-fdq"])  # keeps ignored node_modules
    # Every task predates Hono's move to pnpm, so all bases install with bun.
    lock = hashlib.md5((WORK / "bun.lock").read_bytes()).hexdigest()
    if lock != _installed_lock:
        sh(BUN + ["install", "--frozen-lockfile"], timeout=900)
        _installed_lock = lock


def run_tests(files):
    r = sh(VITEST + files, check=False, timeout=900)
    log = (r.stdout + r.stderr)[-4000:]
    # Results are published: keep local paths out of them.
    for p in (str(WORK), str(WORK).replace("\\", "/"), str(Path.home()), str(Path.home()).replace("\\", "/")):
        log = log.replace(p, "<local>")
    return r.returncode == 0, log


def install_right_size():
    """Install the right-size skill and the subagents right-size-setup would generate."""
    skills = WORK / ".claude" / "skills"
    agents = WORK / ".claude" / "agents"
    skills.mkdir(parents=True, exist_ok=True)
    agents.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "skills" / "right-size", skills / "right-size", dirs_exist_ok=True)
    tiers = yaml.safe_load((ROOT / "skills/right-size/harnesses/claude-code.yaml").read_text(encoding="utf-8"))["tiers"]
    for tier in ("scout", "mechanical", "standard", "deep"):
        tpl = (ROOT / f"skills/right-size-setup/templates/claude-code/right-size-{tier}.md").read_text(encoding="utf-8")
        effort = tiers[tier].get("effort")
        out = (tpl.replace("{{model}}", tiers[tier]["model"])
                  .replace("{{effort_line}}", f"effort: {effort}\n" if effort else ""))
        (agents / f"right-size-{tier}.md").write_text(out, encoding="utf-8")


def claude_cmd(cfg):
    cmd = [shutil.which("claude") or "claude", "-p", "--output-format", "stream-json", "--verbose",
           "--model", cfg["model"], "--setting-sources", "project", "--strict-mcp-config",
           "--no-session-persistence", "--permission-mode", "dontAsk",
           "--allowedTools", *ALLOWED_TOOLS]
    if cfg["effort"]:
        cmd += ["--effort", cfg["effort"]]
    if cfg["right_size"]:
        cmd += ["--append-system-prompt", DELEGATE_NUDGE if cfg.get("nudge") == "delegate" else RIGHT_SIZE_NUDGE]
    return cmd


def run_router(task, log_dir, tier=None, split=False, escalations=None):
    """Run a task through route.py and fold its runs into one result-like dict.

    Cost includes the classifier call. Sessions must persist so that an
    escalation can resume them, so --no-session-persistence is left out.
    """
    cmd = [sys.executable, str(ROUTER), "--print", "--json", "--log", str(log_dir),
           *(["--tier", tier] if tier else []), *(["--split"] if split else []),
           *(["--max-escalations", str(escalations)] if escalations is not None else []),
           task["prompt"] + PROMPT_SUFFIX, "--",
           "--setting-sources", "project", "--strict-mcp-config", "--permission-mode", "dontAsk",
           "--allowedTools", *ALLOWED_TOOLS]
    try:
        r = subprocess.run(cmd, cwd=WORK, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {}, True
    try:
        summary = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"router failed on {task['id']}: {r.stderr[-1500:]}")
    runs = [x["result"] or {} for x in summary["runs"]]
    usage = {}
    # Per-run usage from route.py: a resumed session reports cumulative totals.
    for mu in [(summary["classifier"] or {}).get("model_usage")] + [x.get("model_usage") for x in summary["runs"]]:
        for model, u in (mu or {}).items():
            acc = usage.setdefault(model, {})
            for k, v in u.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    acc[k] = acc.get(k, 0) + v
    last = runs[-1] if runs else {}
    return {
        "api_error_status": next((x.get("api_error_status") for x in runs if x.get("api_error_status")), None),
        "result": last.get("result"),
        "is_error": last.get("is_error"),
        "num_turns": sum(x.get("num_turns") or 0 for x in runs),
        "duration_ms": sum(x.get("duration_ms") or 0 for x in runs),
        "total_cost_usd": ((summary["classifier"] or {}).get("cost_usd") or 0) + sum(x.get("cost_usd") or 0 for x in summary["runs"]),
        "modelUsage": usage,
        "subagent_stats": last.get("subagent_stats"),
        "permission_denials": [d for x in runs for d in (x.get("permission_denials") or [])],
        "route": {"decision": summary["decision"], "profiles": [x["profile"] for x in summary["runs"]],
                  "parts": [{"title": x["title"], "profiles": [r["profile"] for r in x["runs"]],
                             "cost_usd": sum(r["cost_usd"] or 0 for r in x["runs"])}
                            for x in summary.get("parts") or []] or None},
    }, False


def run_one(task, name, out_dir, rep=None):
    cfg = CONFIGS[name]
    stem = f"{task['id']}__{name}" + (f"__r{rep}" if rep else "")
    files = [f for u in units(task) for f in test_files(u)]
    checkout(base_rev(task))
    if cfg["right_size"]:
        install_right_size()

    raw = RAW / out_dir.name
    raw.mkdir(parents=True, exist_ok=True)
    stream_path = raw / f"{stem}.jsonl"
    started = time.time()
    if cfg.get("router"):
        result, timed_out = run_router(task, raw / stem, cfg.get("tier"), cfg.get("split"), cfg.get("escalations"))
    else:
        try:
            r = subprocess.run(claude_cmd(cfg), cwd=WORK, input=task["prompt"] + PROMPT_SUFFIX,
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=TIMEOUT_S)
            stream, timed_out = r.stdout, False
        except subprocess.TimeoutExpired as e:
            stream, timed_out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), True
        stream_path.write_text(stream, encoding="utf-8")
        result = {}
        for line in stream.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                result = ev
    wall = time.time() - started

    if result.get("api_error_status") == 429:
        # Usage limit, not a task failure: record nothing so a rerun picks it up.
        raise SystemExit(f"rate limited on {task['id']} / {name}: {result.get('result')}")

    diff = sh(["git", "diff", "--", ".", ":(exclude)*.test.ts", ":(exclude)*.test.tsx"], check=False).stdout
    (raw / f"{stem}.diff").write_text(diff, encoding="utf-8")

    # Score with the PRs' own tests, overwriting whatever the agent did to them.
    scores = score(task)
    solved = all(ok for ok, _ in scores.values())
    test_log = "\n".join(log[-1500 // len(scores):] for _, log in scores.values())

    record = {
        "task": task["id"], "pr": task["pr"], "config": name, "rep": rep, "expected_tier": task["expected_tier"],
        "solved": solved and not timed_out, "timed_out": timed_out, "wall_s": round(wall, 1),
        "is_error": result.get("is_error"), "num_turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"), "cost_usd": result.get("total_cost_usd"),
        "model_usage": result.get("modelUsage"), "subagents": result.get("subagent_stats"),
        "permission_denials": len(result.get("permission_denials") or []),
        "route": result.get("route"),
        "diff_lines": sum(1 for l in diff.splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---")),
        "parts_solved": {k: ok for k, (ok, _) in scores.items()} if task.get("parts") else None,
        "test_files": files, "test_tail": test_log[-1500:],
    }
    (out_dir / f"{stem}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def validate_batch(t):
    """At the base every part's tests fail; with every part's own fix applied they pass."""
    checkout(t["base"])
    before = score(t)
    patch = RAW / "validate.patch"  # a file, not stdin: text-mode pipes add CRs on Windows
    patch.parent.mkdir(parents=True, exist_ok=True)
    for u in units(t):
        sh(["git", "diff", f"--output={patch}", f"{u['solution']}^", u["solution"], "--", "src",
            ":(exclude)*.test.ts", ":(exclude)*.test.tsx"])
        sh(["git", "apply", str(patch)])
    after = score(t)
    valid = True
    for u in units(t):
        b, a = before[u["id"]][0], after[u["id"]][0]
        valid &= (not b) and a
        print(f"  {u['id']:<20} fail-before={not b} pass-after={a}")
        if not a:
            print(after[u["id"]][1][-800:])
    print(f"{t['id']:<22} {'OK' if valid else 'INVALID'}")
    return valid


def cmd_validate(args):
    ok = True
    for t in load_tasks(args.tasks, args.set):
        if t.get("parts"):
            ok &= validate_batch(t)
            continue
        files = test_files(t)
        checkout(f"{t['solution']}^")
        sh(["git", "checkout", t["solution"], "--", *files])
        before, _ = run_tests(files)
        checkout(t["solution"])
        after, log = run_tests(files)
        valid = (not before) and after
        ok &= valid
        print(f"{t['id']:<22} tests={len(files)} fail-before={not before} pass-after={after} {'OK' if valid else 'INVALID'}")
        if not after:
            print(log[-800:])
    sys.exit(0 if ok else 1)


def cmd_run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    configs = args.configs.split(",") if args.configs else list(CONFIGS)
    meta = {"started": datetime.now(timezone.utc).isoformat(), "configs": {c: CONFIGS[c] for c in configs},
            "allowed_tools": ALLOWED_TOOLS, "nudge": RIGHT_SIZE_NUDGE, "delegate_nudge": DELEGATE_NUDGE,
            "claude_version": sh(["claude", "--version"], check=False).stdout.strip()}
    if (out / "meta.json").exists():
        # A later batch of runs into the same folder adds to the record instead of replacing it.
        prev = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        meta["started"] = prev.get("started", meta["started"])
        meta["configs"] = {**prev.get("configs", {}), **meta["configs"]}
        if prev.get("claude_version") not in (None, meta["claude_version"]):
            meta["claude_version"] = f"{prev['claude_version']} / {meta['claude_version']}"
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    tasks = load_tasks(args.tasks, args.set)
    # Repetitions outermost, configs innermost: every configuration sees each task
    # at about the same time of day, and a stopped run still leaves complete reps.
    for r in range(1, args.reps + 1):
        for t in tasks:
            for name in configs:
                rep = r if args.reps > 1 else None
                stem = f"{t['id']}__{name}" + (f"__r{rep}" if rep else "")
                if (out / f"{stem}.json").exists() and not args.force:
                    print(f"skip {stem} (done)")
                    continue
                rec = run_one(t, name, out, rep)
                print(f"{stem:<40} solved={rec['solved']} cost=${rec['cost_usd']:.2f} wall={rec['wall_s']}s "
                      f"subagents={(rec['subagents'] or {}).get('spawned')}", flush=True)
    sh(["git", "checkout", "-f", "-q", "origin/main"])
    sh(["git", "clean", "-fdq"])


def tokens(mu):
    t = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    for m in (mu or {}).values():
        t["input"] += m.get("inputTokens", 0)
        t["output"] += m.get("outputTokens", 0)
        t["cache_read"] += m.get("cacheReadInputTokens", 0)
        t["cache_write"] += m.get("cacheCreationInputTokens", 0)
    t["total"] = sum(t.values())
    return t


def escalated(r):
    """Whether a routed run escalated. A split run has one profile per part, so count within parts."""
    route = r.get("route") or {}
    if route.get("parts"):
        return any(len(x["profiles"]) > 1 for x in route["parts"])
    return len(route.get("profiles") or []) > 1


def cmd_summarize(args):
    d = Path(args.dir)
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*__*.json"))]
    configs = list(dict.fromkeys(r["config"] for r in recs))
    lines = ["| Task | Expected tier | " + " | ".join(configs) + " |",
             "|---|---|" + "---|" * len(configs)]
    for task in dict.fromkeys(r["task"] for r in recs):
        cells = []
        for c in configs:
            rs = [x for x in recs if x["task"] == task and x["config"] == c]
            if not rs:
                cells.append("–")
                continue
            ok = sum(x["solved"] for x in rs)
            cost = sum(x["cost_usd"] or 0 for x in rs) / len(rs)
            wall = sum(x["wall_s"] for x in rs) / len(rs)
            models = "+".join(sorted({m.split("-")[1] for x in rs for m in (x["model_usage"] or {})}))
            mark = "✅" if ok == len(rs) else ("❌" if ok == 0 else "⚠️")
            cells.append(f"{mark} {ok}/{len(rs)} · ${cost:.2f} · {wall:.0f}s · {models}")
        exp = next(x["expected_tier"] for x in recs if x["task"] == task)
        lines.append(f"| {task} | {exp} | " + " | ".join(cells) + " |")
    lines += ["", "Cells: solved runs / runs · mean cost per run · mean wall time · models used."]
    totals = ["", "| Config | Solved | Total cost | Cost per solved task | Mean cost per run | Escalations | "
              "Total tokens | Total time |", "|---|---|---|---|---|---|---|---|"]
    agg = {}
    for c in configs:
        rs = [r for r in recs if r["config"] == c]
        solved = sum(r["solved"] for r in rs)
        cost = sum(r["cost_usd"] or 0 for r in rs)
        tok = sum(tokens(r["model_usage"])["total"] for r in rs)
        wall = sum(r["wall_s"] for r in rs)
        esc = sum(escalated(r) for r in rs)
        agg[c] = {"runs": len(rs), "solved": solved, "cost_usd": round(cost, 4), "tokens": tok,
                  "wall_s": round(wall, 1), "escalations": esc}
        cps = f"${cost / solved:.2f}" if solved else "–"
        totals.append(f"| {c} | {solved}/{len(rs)} | ${cost:.2f} | {cps} | ${cost / len(rs):.2f} | "
                      f"{esc if any(r.get('route') for r in rs) else '–'} | {tok/1e6:.2f}M | {wall/60:.0f} min |")
    md = "\n".join(lines + totals) + "\n"
    (d / "summary.md").write_text(md, encoding="utf-8")
    (d / "summary.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")
    print(md)


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # summaries and test logs aren't cp1252-safe
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("--tasks"); v.add_argument("--set")
    r = sub.add_parser("run"); r.add_argument("--out", required=True); r.add_argument("--configs")
    r.add_argument("--tasks"); r.add_argument("--set"); r.add_argument("--force", action="store_true")
    r.add_argument("--reps", type=int, default=1)
    s = sub.add_parser("summarize"); s.add_argument("dir")
    args = p.parse_args()
    {"validate": cmd_validate, "run": cmd_run, "summarize": cmd_summarize}[args.cmd](args)


if __name__ == "__main__":
    main()
