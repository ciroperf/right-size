"""right-size-audit on a fake transcript folder. No model calls."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "right-size-audit" / "scripts"))
import audit  # noqa: E402

PRICES, TIERS = audit.load_prices()
STANDARD = next(m for m in PRICES if TIERS["standard"] in m)
DEEP = next(m for m in PRICES if TIERS["deep"] in m)


def call(mid, model, usage, content=(), ts="2026-10-21T10:00:00Z"):
    return {"type": "assistant", "timestamp": ts, "effort": "medium",
            "message": {"id": mid, "model": model, "usage": usage, "content": list(content)}}


def write(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")


class Audit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "proj"
        edit = {"type": "tool_use", "name": "Edit", "input": {}}
        write(self.dir / "s1.jsonl", [
            {"type": "user", "message": {"role": "user", "content": "fix it"}},
            # Streaming writes one line per content block with the same id: counted once.
            call("m1", DEEP, {"input_tokens": 1000, "output_tokens": 100}),
            call("m1", DEEP, {"input_tokens": 1000, "output_tokens": 100}, [edit]),
            # A switch to another model re-reads the conversation into a new cache.
            call("m2", STANDARD, {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 1_000_000}),
            call("m3", "<synthetic>", {"input_tokens": 5, "output_tokens": 5}),
            call("m4", "claude-unknown-9", {"input_tokens": 5, "output_tokens": 5}),
        ])
        write(self.dir / "s1" / "subagents" / "agent-a.jsonl", [
            call("x1", DEEP, {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 1_000_000}),
        ])
        (self.dir / "s1" / "subagents" / "agent-a.meta.json").write_text('{"agentType": "Explore"}', encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_audit(self, since=None):
        return audit.audit([self.dir], since, PRICES, STANDARD)

    def test_prices_each_call_once_by_token_kind(self):
        by_model, by_kind, *_ = self.run_audit()
        p = PRICES[DEEP]
        self.assertAlmostEqual(by_model[DEEP]["input"], 1000 * p["input"] / 1e6)
        self.assertAlmostEqual(by_model[DEEP]["output"], 100 * p["output"] / 1e6)
        self.assertAlmostEqual(by_model[DEEP]["cache_read"], p["cache_read"])  # the subagent's million
        self.assertEqual(by_model[DEEP]["calls"], 2)
        self.assertAlmostEqual(by_kind["cache_write"], 1.25 * PRICES[STANDARD]["input"])  # 5-minute TTL

    def test_one_hour_cache_writes_cost_double(self):
        usage = {"cache_creation_input_tokens": 1_000_000,
                 "cache_creation": {"ephemeral_1h_input_tokens": 1_000_000}}
        self.assertAlmostEqual(audit.call_cost(usage, PRICES[STANDARD])["cache_write"], 2 * PRICES[STANDARD]["input"])

    def test_switches_subagents_and_unpriced(self):
        _, _, by_agent, switches, sessions, unpriced = self.run_audit()
        self.assertEqual([(s["from"], s["to"]) for s in switches], [(DEEP, STANDARD)])
        self.assertIn(("Explore", DEEP), by_agent)
        self.assertEqual(dict(unpriced), {"claude-unknown-9": 1})  # <synthetic> is not a model call
        self.assertEqual(sessions[0]["edits"], 1)

    def test_since_filters_old_calls(self):
        from datetime import datetime, timezone
        *_, sessions, _ = self.run_audit(since=datetime(2026, 10, 22, tzinfo=timezone.utc))
        self.assertEqual(sessions, [])

    def test_report_names_the_levers(self):
        text = audit.report(*self.run_audit(), PRICES, TIERS, 30)
        self.assertIn("Output tokens are", text)
        self.assertIn("1 model switch inside", text)
        self.assertIn("Subagents spent", text)
        self.assertIn("claude-unknown-9", text)


if __name__ == "__main__":
    unittest.main()
