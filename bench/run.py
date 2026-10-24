"""right-size benchmark runner.

Usage:
  python bench/run.py validate [--tasks id,id]
  python bench/run.py run --out bench/results/<name> [--configs a,b] [--tasks id,id]
  python bench/run.py summarize bench/results/<name> [more result dirs to pool]

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
    # The difficulty floor: the cheapest writing tier alone, no checks, no escalation.
    # Its solve rate over reps is the measured difficulty of each task.
    "haiku": {"model": "haiku", "effort": "low", "right_size": False},
    "right-size": {"model": "opus", "effort": None, "right_size": True},
    # The router's classifier picks model and effort for the whole session before it starts
    # (skills/right-size/scripts/route.py --classify), then checks escalate. Since 2026-10-21
    # the router's default is the ladder below; this config keeps measuring the classifier.
    "router": {"model": None, "effort": None, "right_size": False, "router": True, "classify": True},
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
    # Read-only commands and cleanup, so compound commands (cd x && npx vitest ...) and
    # removing a scratch test are not denied. No installs: they would change node_modules.
    "Bash(cd *)", "Bash(ls *)", "Bash(cat *)", "Bash(head *)", "Bash(tail *)", "Bash(grep *)",
    "Bash(wc *)", "Bash(rm *)",
]

# What route.py runs after each attempt: the existing tests related to the files the agent
# changed. The PR's own tests are never visible here; they are copied in only to score.
VERIFY_CMD = "npx vitest --run --changed --passWithNoTests --coverage.enabled=false"

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
    # A task lists its tests when the PR only changed a shared case file that other test files import.
    if task.get("test_files"):
        return list(task["test_files"])
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


def lockfile():
    # Hono moved from bun to pnpm on 2026-09-24 (#5433); later task bases use pnpm.
    pnpm = WORK / "pnpm-lock.yaml"
    return pnpm if pnpm.exists() else WORK / "bun.lock"


def install_cmd():
    """The frozen install for the checked-out commit, with its pinned package manager."""
    if lockfile().name == "bun.lock":
        return BUN + ["install", "--frozen-lockfile"]
    pm = json.loads((WORK / "package.json").read_text(encoding="utf-8")).get("packageManager", "pnpm@10")
    return ["npx", "-y", pm.split("+")[0], "install", "--frozen-lockfile"]


def checkout(rev):
    """Clean checkout of rev, reinstalling dependencies only if the lockfile changed."""
    global _installed_lock
    sh(["git", "checkout", "-f", "-q", rev])
    sh(["git", "clean", "-fdq"])  # keeps ignored node_modules
    install = install_cmd()
    lock = (install[2], hashlib.md5(lockfile().read_bytes()).hexdigest())
    if lock != _installed_lock:
        if _installed_lock and _installed_lock[0] != lock[0]:
            # bun and pnpm lay out node_modules differently: switching needs a clean slate.
            shutil.rmtree(WORK / "node_modules", ignore_errors=True)
        sh(install, timeout=900)
        _installed_lock = lock
    # Checked on every checkout: an incremental install once left vitest resolving an old
    # top-level vite, and an agent's rm could break node_modules. Either way, start clean.
    if not vitest_starts():
        shutil.rmtree(WORK / "node_modules", ignore_errors=True)
        sh(install, timeout=900)
        if not vitest_starts():
            raise SystemExit(f"vitest does not start after a clean install at {rev}")


def vitest_starts():
    """Start vitest for real (config and vite load) without running any test."""
    r = sh(VITEST + ["--passWithNoTests", "no-such-test-file"], check=False, timeout=300)
    return r.returncode == 0 and not any(e in r.stdout + r.stderr for e in ENV_ERRORS)


# vitest failing before any test runs: a broken environment, not a failed fix.
ENV_ERRORS = ("Startup Error", "ERR_PACKAGE_PATH_NOT_EXPORTED")


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


def run_router(task, log_dir, tier=None, split=False, escalations=None, classify=False):
    """Run a task through route.py and fold its runs into one result-like dict.

    Cost includes the classifier call. Sessions must persist so that an
    escalation can resume them, so --no-session-persistence is left out.
    """
    cmd = [sys.executable, str(ROUTER), "--print", "--json", "--log", str(log_dir),
           *(["--tier", tier] if tier else []), *(["--split"] if split else []),
           *(["--classify"] if classify else []),
           *(["--max-escalations", str(escalations)] if escalations is not None else []),
           *(["--verify-cmd", VERIFY_CMD] if VERIFY_CMD else []),
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
    checks = [c for x in summary["runs"] for c in x.get("checks") or []]
    for mu in ([(summary["classifier"] or {}).get("model_usage")] + [x.get("model_usage") for x in summary["runs"]]
               + [c.get("model_usage") for c in checks]):
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
        "total_cost_usd": (((summary["classifier"] or {}).get("cost_usd") or 0)
                           + sum(x.get("cost_usd") or 0 for x in summary["runs"])
                           + sum(c.get("cost_usd") or 0 for c in checks)),
        "modelUsage": usage,
        "subagent_stats": last.get("subagent_stats"),
        "permission_denials": [d for x in runs for d in (x.get("permission_denials") or [])],
        "route": {"decision": summary["decision"], "profiles": [x["profile"] for x in summary["runs"]],
                  "checks": [{k: c.get(k) for k in ("kind", "ok", "reason", "cost_usd", "probed", "denied")} for c in checks],
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
        result, timed_out = run_router(task, raw / stem, cfg.get("tier"), cfg.get("split"), cfg.get("escalations"),
                                       cfg.get("classify", False))
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
    if any(e in log for _, log in scores.values() for e in ENV_ERRORS):
        # Like a usage limit: record nothing so a rerun picks it up.
        raise SystemExit(f"test environment broken on {task['id']} / {name}: vitest did not start")
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
            "claude_version": sh(["claude", "--version"], check=False).stdout.strip(),
            # The router version under test: published numbers come from one commit, unmodified.
            "router_commit": sh(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).stdout.strip()
                             + ("-dirty" if sh(["git", "status", "--porcelain", "skills"], cwd=ROOT).stdout.strip()
                                else "")}
    if (out / "meta.json").exists():
        # A later batch of runs into the same folder adds to the record instead of replacing it.
        prev = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        meta["started"] = prev.get("started", meta["started"])
        meta["configs"] = {**prev.get("configs", {}), **meta["configs"]}
        if prev.get("router_commit") not in (None, meta["router_commit"]):
            meta["router_commit"] = f"{prev['router_commit']} / {meta['router_commit']}"
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


def gold_size(task):
    """Lines and files the merged PR changed outside tests: the task's size, independent of any agent."""
    files = lines = 0
    for u in units(task):
        out = sh(["git", "diff", "--numstat", f"{u['solution']}^", u["solution"], "--", "src",
                  ":(exclude)*.test.ts", ":(exclude)*.test.tsx"], check=False).stdout
        for row in out.splitlines():
            add, rem, _ = row.split("\t", 2)
            files += 1
            lines += int(add) + int(rem) if add.isdigit() and rem.isdigit() else 0
    return files, lines


def spread(xs):
    """mean, sample standard deviation, min, max."""
    m = sum(xs) / len(xs)
    sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5 if len(xs) > 1 else 0.0
    return m, sd, min(xs), max(xs)


FLOOR = "haiku"


def cmd_summarize(args):
    """Per-task cells, then totals that keep difficulty and variance visible.

    - Difficulty comes from outside the configs being compared: the merged PR's size,
      and the solve rate of the `haiku` floor config when it ran.
    - Totals count only tasks every config ran, so no config is compared on an easier set.
    - With reps, totals are per rep, reported as mean ± sd and min–max.
    """
    d = Path(args.dirs[0])
    # A later dir replaces an earlier one's run of the same task, config and rep (a rerun).
    pooled = {}
    for x in args.dirs:
        for p in sorted(Path(x).glob("*__*.json")):
            r = json.loads(p.read_text(encoding="utf-8"))
            r["rep"] = r.get("rep") or 1  # single-rep runs record no rep
            pooled[(r["task"], r["config"], r["rep"])] = r
    recs = list(pooled.values())
    configs = (list(dict.fromkeys(r["config"] for r in recs if r["config"] != FLOOR))
               or [FLOOR])  # a floor-only run summarizes the floor itself
    tasks_by_id = {t["id"]: t for t in load_tasks()}
    tids = list(dict.fromkeys(r["task"] for r in recs))
    by = {}
    for r in recs:
        by.setdefault((r["task"], r["config"]), []).append(r)

    def floor_rate(tid):
        rs = by.get((tid, FLOOR))
        return (sum(x["solved"] for x in rs), len(rs)) if rs else None

    def bucket(tid):
        fr = floor_rate(tid)
        if not fr:
            return "unknown"
        return "easy: floor solves" if fr[0] * 2 > fr[1] else "hard: floor fails half or more"

    size = {}
    for tid in tids:
        try:
            size[tid] = gold_size(tasks_by_id[tid]) if WORK.exists() else None
        except (KeyError, subprocess.CalledProcessError, ValueError):
            size[tid] = None

    lines = ["| Task | PR size (files · lines) | Haiku alone | " + " | ".join(configs) + " |",
             "|---|---|---|" + "---|" * len(configs)]
    for tid in tids:
        cells = []
        for c in configs:
            rs = by.get((tid, c))
            if not rs:
                cells.append("–")
                continue
            ok = sum(x["solved"] for x in rs)
            m, _, lo, hi = spread([x["cost_usd"] or 0 for x in rs])
            models = "+".join(sorted({m_.split("-")[1] for x in rs for m_ in (x["model_usage"] or {})}))
            mark = "✅" if ok == len(rs) else ("❌" if ok == 0 else "⚠️")
            rng = f" ({lo:.2f}–{hi:.2f})" if len(rs) > 1 else ""
            cells.append(f"{mark} {ok}/{len(rs)} · ${m:.2f}{rng} · {models}")
        sz = size.get(tid)
        fr = floor_rate(tid)
        lines.append(f"| {tid} | {f'{sz[0]} · {sz[1]}' if sz else '?'} | {f'{fr[0]}/{fr[1]}' if fr else '–'} | "
                     + " | ".join(cells) + " |")
    lines += ["", "Cells: solved runs / runs · mean cost per run (min–max over reps) · models used. "
              "PR size: source files and lines the merged fix changed, tests excluded. "
              "Haiku alone: solve rate of the `haiku` floor config (Haiku, low effort, no checks)."]

    common = [t for t in tids if all((t, c) in by for c in configs)]
    dropped = [t for t in tids if t not in common and any((t, c) in by for c in configs)]
    totals = ["", f"Totals over the {len(common)} tasks every config ran"
              + (f" (left out: {', '.join(dropped)})" if dropped else "") + ".", "",
              "| Config | Solved per rep | Cost per rep | Cost per solved task | Escalations | Total time |",
              "|---|---|---|---|---|---|"]
    agg = {}
    for c in configs:
        rs = [r for t in common for r in by[(t, c)]]
        reps = sorted({r.get("rep") or 1 for r in rs})
        per = [[r for r in rs if (r.get("rep") or 1) == k] for k in reps]
        solved = [sum(r["solved"] for r in p) for p in per]
        cost = [sum(r["cost_usd"] or 0 for r in p) for p in per]
        sm, ssd, slo, shi = spread(solved)
        cm, csd, clo, chi = spread(cost)
        esc = sum(escalated(r) for r in rs)
        wall = sum(r["wall_s"] for r in rs)
        agg[c] = {"tasks": len(common), "reps": len(reps), "solved_per_rep": solved,
                  "cost_per_rep": [round(x, 4) for x in cost], "escalations": esc, "wall_s": round(wall, 1)}
        var = len(reps) > 1
        s_txt = f"{sm:.1f} ± {ssd:.1f} of {len(common)} ({slo}–{shi})" if var else f"{solved[0]}/{len(common)}"
        c_txt = f"${cm:.2f} ± {csd:.2f} (${clo:.2f}–${chi:.2f})" if var else f"${cost[0]:.2f}"
        cps = f"${sum(cost) / sum(solved):.2f}" if sum(solved) else "–"
        totals.append(f"| {c} | {s_txt} | {c_txt} | {cps} | {esc if any(r.get('route') for r in rs) else '–'} "
                      f"| {wall / 60:.0f} min |")
    if max((r["rep"] for r in recs), default=1) <= 1:
        totals += ["", "One run per cell: a difference of one task between configs can be noise."]

    buckets = list(dict.fromkeys(bucket(t) for t in common))
    if buckets != ["unknown"]:
        totals += ["", "By difficulty (from the `haiku` floor runs):", "",
                   "| Config | " + " | ".join(f"{b} ({sum(bucket(t) == b for t in common)} tasks)" for b in buckets)
                   + " |", "|---|" + "---|" * len(buckets)]
        for c in configs:
            cells = []
            for b in buckets:
                rs = [r for t in common if bucket(t) == b for r in by[(t, c)]]
                ok = sum(r["solved"] for r in rs)
                cells.append(f"{ok}/{len(rs)} solved · ${sum(r['cost_usd'] or 0 for r in rs) / len(rs):.2f} per run")
            totals.append(f"| {c} | " + " | ".join(cells) + " |")
            agg[c]["by_difficulty"] = cells
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
    s = sub.add_parser("summarize"); s.add_argument("dirs", nargs="+")  # first dir gets summary.md
    args = p.parse_args()
    {"validate": cmd_validate, "run": cmd_run, "summarize": cmd_summarize}[args.cmd](args)


if __name__ == "__main__":
    main()
