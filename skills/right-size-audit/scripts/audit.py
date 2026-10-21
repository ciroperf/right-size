#!/usr/bin/env python3
"""right-size audit: where did this project's Claude Code spend go?

Reads the session transcripts Claude Code keeps on disk (~/.claude/projects),
prices every model call at list price, and reports what drove the cost: which
models, which token kinds, subagents, and model switches that re-read a whole
conversation uncached. No model calls, nothing leaves the machine.

Usage:
  python audit.py                  # the project in the current directory, last 30 days
  python audit.py --days 7
  python audit.py --project PATH   # another project
  python audit.py --all            # every project
  python audit.py --json           # machine-readable summary

List prices are an estimate of what the tokens are worth, not of a bill: on a
subscription plan they show relative weight, not money spent.

Standard library only, so it runs wherever the skill is installed.
"""

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RIGHT_SIZE = HERE.parent.parent / "right-size"
sys.path.insert(0, str(RIGHT_SIZE / "scripts"))
from route import read_yaml  # noqa: E402  (the right-size skill's reader: stdlib only)

KINDS = ["input", "cache_write", "cache_read", "output"]
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def load_prices():
    path = RIGHT_SIZE / "harnesses" / "claude-code.yaml"
    if not path.exists():
        sys.exit("right-size-audit: the right-size skill isn't installed next to this one; install it first")
    hmap = read_yaml(path)
    prices = {m: {k: float(v) for k, v in p.items()} for m, p in (hmap.get("prices") or {}).items()}
    tiers = {t: (e or {}).get("model") for t, e in hmap["tiers"].items()}
    return prices, tiers


def price_for(model, prices):
    if model in prices:
        return prices[model]
    for known, p in prices.items():  # dated or suffixed ids, e.g. claude-opus-5-5-20261001
        if model.startswith(known):
            return p
    return None


def call_cost(usage, p):
    """List-price cost of one model call, split by token kind."""
    cc = usage.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens") or 0
    w5m = (usage.get("cache_creation_input_tokens") or 0) - w1h
    m = 1e-6
    return {
        "input": (usage.get("input_tokens") or 0) * p["input"] * m,
        "cache_write": (w5m * 1.25 + w1h * 2) * p["input"] * m,
        "cache_read": (usage.get("cache_read_input_tokens") or 0) * p["cache_read"] * m,
        "output": (usage.get("output_tokens") or 0) * p["output"] * m,
    }


def project_dirs(args):
    base = Path.home() / ".claude" / "projects"
    if args.all:
        return sorted(d for d in base.iterdir() if d.is_dir())
    root = Path(args.project or ".").resolve()
    if not args.project:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, cwd=root)
        if top.returncode == 0:
            root = Path(top.stdout.strip()).resolve()
    # Claude Code names a project's folder after its path, every non-alphanumeric character a dash.
    d = base / re.sub(r"[^A-Za-z0-9]", "-", str(root))
    if not d.is_dir():
        sys.exit(f"right-size-audit: no Claude Code transcripts for {root} (looked in {d})")
    return [d]


def read_calls(path, since):
    """One record per model call: streaming writes a message once per content block, so keep the last."""
    calls, order = {}, []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = e.get("message") or {}
            if e.get("type") != "assistant" or not msg.get("usage") or not msg.get("model"):
                continue
            ts = e.get("timestamp")
            if since and ts and datetime.fromisoformat(ts.replace("Z", "+00:00")) < since:
                continue
            mid = msg.get("id") or e.get("uuid")
            if mid not in calls:
                order.append(mid)
                calls[mid] = {"model": msg["model"], "usage": msg["usage"], "effort": e.get("effort"),
                              "edits": 0, "ts": ts}
            else:
                calls[mid]["usage"] = msg["usage"]
            calls[mid]["edits"] += sum(1 for b in msg.get("content") or []
                                       if isinstance(b, dict) and b.get("type") == "tool_use"
                                       and b.get("name") in EDIT_TOOLS)
    return [calls[m] for m in order]


def audit(dirs, since, prices, standard=None):
    """Totals by model, token kind and subagent, plus model switches and per-session costs.

    `standard` is the standard tier's model id: each session also gets what its
    tokens would cost there (same tokens, so a ceiling on the saving, not a
    prediction: a smaller model can need more turns).
    """
    by_model = defaultdict(lambda: defaultdict(float))
    by_kind = defaultdict(float)
    by_agent = defaultdict(lambda: defaultdict(float))
    unpriced = defaultdict(int)
    switches = []
    sessions = []
    for d in dirs:
        for main in sorted(d.glob("*.jsonl")):
            calls = read_calls(main, since)
            subs = []
            for sub in sorted((d / main.stem / "subagents").glob("*.jsonl")):
                meta = sub.with_name(sub.stem + ".meta.json")
                kind = "subagent"
                if meta.exists():
                    try:
                        kind = json.loads(meta.read_text(encoding="utf-8")).get("agentType") or kind
                    except json.JSONDecodeError:
                        pass
                subs.append((kind, read_calls(sub, since)))
            if not calls and not any(c for _, c in subs):
                continue
            s = {"project": d.name, "session": main.stem, "cost": 0.0, "models": defaultdict(float),
                 "edits": 0, "calls": len(calls), "subagent_cost": 0.0, "as_standard": 0.0}
            prev = None
            for agent, cs in [("main", calls)] + subs:
                for c in cs:
                    if c["model"].startswith("<"):  # e.g. <synthetic>: client-side messages, no model call
                        continue
                    p = price_for(c["model"], prices)
                    if p is None:
                        unpriced[c["model"]] += 1
                        continue
                    cost = call_cost(c["usage"], p)
                    total = sum(cost.values())
                    for k, v in cost.items():
                        by_kind[k] += v
                        by_model[c["model"]][k] += v
                    by_model[c["model"]]["calls"] += 1
                    s["cost"] += total
                    s["models"][c["model"]] += total
                    s["edits"] += c["edits"]
                    if standard:
                        s["as_standard"] += sum(call_cost(c["usage"], prices[standard]).values())
                    if agent == "main":
                        # A model switch in the main thread re-reads the conversation without cache.
                        if prev and prev != c["model"] and (c["usage"].get("cache_creation_input_tokens") or 0) > 0:
                            switches.append({"session": main.stem, "from": prev, "to": c["model"],
                                             "cost": cost["cache_write"] + cost["input"]})
                        prev = c["model"]
                    else:
                        s["subagent_cost"] += total
                        by_agent[(agent, c["model"])]["cost"] += total
                        by_agent[(agent, c["model"])]["calls"] += 1
            sessions.append(s)
    return by_model, by_kind, by_agent, switches, sessions, unpriced


def report(by_model, by_kind, by_agent, switches, sessions, unpriced, prices, tiers, days):
    total = sum(by_kind.values())
    out = []
    if total == 0:
        return "right-size audit: no priced model calls in this period."
    pct = lambda x: f"{100 * x / total:.0f}%"
    out.append(f"right-size audit · {len(sessions)} sessions · last {days} days · ${total:.2f} at list price")
    out.append("")
    out.append("By model")
    for m, v in sorted(by_model.items(), key=lambda kv: -sum(kv[1][k] for k in KINDS)):
        c = sum(v[k] for k in KINDS)
        out.append(f"  {m:<22} ${c:>8.2f}  {pct(c):>4}  {int(v['calls'])} calls")
    out.append("")
    out.append("By token kind")
    for k in KINDS:
        out.append(f"  {k:<12} ${by_kind[k]:>8.2f}  {pct(by_kind[k]):>4}")
    findings = []
    out_share = by_kind["output"] / total
    findings.append(f"Output tokens are {out_share:.0%} of spend: shorter replies can save at most that much. "
                    f"Input and cache are {1 - out_share:.0%}: model choice and how much context each call "
                    f"carries move the bill.")
    if switches:
        sc = sum(x["cost"] for x in switches)
        findings.append(f"{len(switches)} model switch{'es' if len(switches) != 1 else ''} inside a conversation cost ${sc:.2f} in uncached "
                        f"re-reads. Switch models at the start of a session, or change effort instead "
                        f"(effort changes keep the cache).")
    sub = sum(s["subagent_cost"] for s in sessions)
    if sub:
        top = sorted(by_agent.items(), key=lambda kv: -kv[1]["cost"])[:3]
        names = ", ".join(f"{a} on {m} ${v['cost']:.2f}" for (a, m), v in top)
        findings.append(f"Subagents spent ${sub:.2f} ({pct(sub)}). Largest: {names}.")
    deep, standard = tiers.get("deep"), tiers.get("standard")
    std_id = next((m for m in prices if standard and standard in m), None)
    if std_id:
        heavy = [s for s in sessions if s["models"] and all(price_for(m, prices)["input"] > prices[std_id]["input"]
                                                             for m in s["models"])]
        small = [s for s in heavy if s["edits"] <= 3]
        if small:
            cost = sum(s["cost"] for s in small)
            alt = sum(s["as_standard"] for s in small)
            findings.append(f"{len(small)} sessions ran only above the standard tier yet edited files 3 times "
                            f"or fewer: ${cost:.2f}. The same tokens on {std_id} would cost about "
                            f"${alt:.2f} (an upper bound on the saving: a smaller model can need "
                            f"more turns). Candidates for a standard default with escalation on failure; "
                            f"right-size-defaults sets it.")
    if unpriced:
        findings.append("No price for: " + ", ".join(f"{m} ({n} calls)" for m, n in unpriced.items())
                        + ". Add it to the right-size skill's harnesses/claude-code.yaml.")
    out.append("")
    out.append("Findings")
    out += [f"  - {f}" for f in findings]
    costly = sorted(sessions, key=lambda s: -s["cost"])[:5]
    out.append("")
    out.append("Costliest sessions")
    for s in costly:
        models = ", ".join(sorted(s["models"], key=lambda m: -s["models"][m]))
        out.append(f"  {s['session'][:8]}  ${s['cost']:>7.2f}  {s['calls']} calls  {s['edits']} edits  {models}")
    return "\n".join(out)


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    prices, tiers = load_prices()
    since = datetime.now(timezone.utc) - timedelta(days=args.days) if args.days else None
    std_id = next((m for m in prices if tiers.get("standard") and tiers["standard"] in m), None)
    by_model, by_kind, by_agent, switches, sessions, unpriced = audit(project_dirs(args), since, prices, std_id)
    if args.json:
        print(json.dumps({
            "days": args.days,
            "total_usd": sum(by_kind.values()),
            "by_model": {m: dict(v) for m, v in by_model.items()},
            "by_kind": dict(by_kind),
            "subagents": [{"agent": a, "model": m, **v} for (a, m), v in by_agent.items()],
            "model_switches": switches,
            "sessions": [{**s, "models": dict(s["models"])} for s in sessions],
            "unpriced": dict(unpriced),
        }, indent=2))
    else:
        print(report(by_model, by_kind, by_agent, switches, sessions, unpriced, prices, tiers, args.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
