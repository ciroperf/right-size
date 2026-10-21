"""Unit tests for skills/right-size/scripts/route.py. No model calls.

Run: python -m unittest discover -s tests -v
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "right-size"
sys.path.insert(0, str(SKILL / "scripts"))

import route  # noqa: E402


def load(name):
    return route.read_yaml(SKILL / "harnesses" / f"{name}.yaml")


TIERS_YAML = route.read_yaml(SKILL / "tiers.yaml")
CLAUDE = load("claude-code")
CODEX = load("codex")


class ReadYaml(unittest.TestCase):
    def test_matches_pyyaml_on_shipped_files(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        files = [SKILL / "tiers.yaml", *sorted((SKILL / "harnesses").glob("*.yaml"))]
        for f in files:
            with self.subTest(file=f.name), mock.patch.dict(sys.modules, {"yaml": None}):
                # PyYAML turns dates into datetime.date; the router only needs strings.
                expected = json.loads(json.dumps(yaml.safe_load(f.read_text(encoding="utf-8")), default=str))
                self.assertEqual(route.read_yaml(f), expected)

    def test_subset(self):
        text = "a: 1\nb:\n  c: x  # comment\n  d: null\n  e: \"q: r\"\nlist:\n  - one\n  - two: three\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.yaml"
            p.write_text(text, encoding="utf-8")
            with mock.patch.dict(sys.modules, {"yaml": None}):
                got = route.read_yaml(p)
        self.assertEqual(got, {"a": 1, "b": {"c": "x", "d": None, "e": "q: r"}, "list": ["one", "two: three"]})


class HarnessMaps(unittest.TestCase):
    def test_router_harnesses_cover_every_tier(self):
        for name, hmap in (("claude-code", CLAUDE), ("codex", CODEX)):
            for tier in route.TIERS:
                with self.subTest(harness=name, tier=tier):
                    self.assertTrue(hmap["tiers"][tier].get("model"))


class Profiles(unittest.TestCase):
    def test_effort_stays_within_one_step_of_the_tier_default(self):
        p = lambda tier, effort: route.profile(tier, effort, CLAUDE, TIERS_YAML)["effort"]
        self.assertEqual(p("standard", None), "medium")
        self.assertEqual(p("standard", "low"), "medium")    # never below the default
        self.assertEqual(p("standard", "high"), "high")     # one step up is allowed
        self.assertEqual(p("mechanical", "high"), "medium")  # two steps up is clamped

    def test_next_profile_respects_the_ceiling(self):
        def nxt(tier, steps, top, effort=None):
            p = route.profile(tier, effort, CLAUDE, TIERS_YAML)
            return route.next_profile(p, steps, top, CLAUDE, TIERS_YAML)
        self.assertEqual(nxt("mechanical", 1, "deep")["tier"], "standard")
        self.assertEqual(nxt("mechanical", 2, "deep")["tier"], "deep")
        self.assertEqual(nxt("mechanical", 2, "standard")["tier"], "standard")
        # At the top tier, effort goes up one step before giving up.
        self.assertEqual(nxt("deep", 1, "deep"), {"tier": "deep", "model": "opus", "effort": "high"})
        self.assertIsNone(nxt("deep", 1, "deep", effort="high"))
        self.assertEqual(nxt("standard", 1, "standard")["effort"], "high")
        self.assertIsNone(nxt("standard", 1, "standard", effort="high"))

    def test_cap(self):
        self.assertEqual(route.cap("deep", "standard"), ("standard", True))
        self.assertEqual(route.cap("mechanical", "standard"), ("mechanical", False))
        self.assertEqual(route.cap("deep", None), ("deep", False))


class Escalation(unittest.TestCase):
    def test_marker(self):
        m = route.MARKER.search("Done.\nRIGHT-SIZE-ESCALATE: verifiable - tests still red")
        self.assertEqual((m.group(1), m.group(2)), ("verifiable", "tests still red"))
        m = route.MARKER.search("RIGHT-SIZE-ESCALATE: reasoning — misread the spec")
        self.assertEqual((m.group(1), m.group(2)), ("reasoning", "misread the spec"))
        self.assertIsNone(route.MARKER.search("All tests pass."))

    def test_notes(self):
        p = route.profile("mechanical", None, CLAUDE, TIERS_YAML)
        nxt = route.profile("standard", None, CLAUDE, TIERS_YAML)
        self.assertIn("RIGHT-SIZE-ESCALATE", route.note(p, "why", nxt, interactive=False))
        self.assertIn("/model sonnet", route.note(p, "why", nxt, interactive=True))
        self.assertIn("highest tier", route.note(p, "why", None, interactive=False))


class Checks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        for cmd in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            route.run(["git", *cmd], cwd=self.root)
        (Path(self.root) / "a.txt").write_text("one\n", encoding="utf-8")
        route.run(["git", "add", "-A"], cwd=self.root)
        route.run(["git", "commit", "-q", "-m", "init"], cwd=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def ck(self, **kw):
        base = {"root": self.root, "verify_cmd": None, "review": "never", "risk_area": None, "top": "deep",
                "harness": "claude-code", "task": "t", "start": route.snapshot(self.root)}
        return {**base, **kw}

    def test_snapshot_sees_edits_and_untracked_files_without_touching_the_index(self):
        start = route.snapshot(self.root)
        self.assertTrue(start)
        (Path(self.root) / "new.txt").write_text("x", encoding="utf-8")
        self.assertNotEqual(route.snapshot(self.root), start)
        self.assertEqual(route.run(["git", "diff", "--cached", "--name-only"], cwd=self.root).stdout, "")

    def test_no_change_fails(self):
        p = route.profile("mechanical", None, CLAUDE, TIERS_YAML)
        reason, recs = route.check_attempt(self.ck(), p, CLAUDE, TIERS_YAML)
        self.assertEqual(reason, "the attempt changed no files")
        scout = route.profile("scout", None, CLAUDE, TIERS_YAML)
        self.assertIsNone(route.check_attempt(self.ck(), scout, CLAUDE, TIERS_YAML)[0])  # read-only

    def test_verify_cmd(self):
        ck = self.ck()
        (Path(self.root) / "a.txt").write_text("two\n", encoding="utf-8")
        p = route.profile("standard", None, CLAUDE, TIERS_YAML)
        fail = f'"{sys.executable}" -c "print(\'boom\'); raise SystemExit(1)"'
        reason, recs = route.check_attempt({**ck, "verify_cmd": fail}, p, CLAUDE, TIERS_YAML)
        self.assertIn("boom", reason)
        ok = f'"{sys.executable}" -c "pass"'
        self.assertIsNone(route.check_attempt({**ck, "verify_cmd": ok}, p, CLAUDE, TIERS_YAML)[0])

    def test_review_rejection_and_outage(self):
        ck = self.ck(review="always")
        (Path(self.root) / "a.txt").write_text("two\n", encoding="utf-8")
        p = route.profile("standard", None, CLAUDE, TIERS_YAML)
        with mock.patch.object(route, "review", return_value=(False, "misses the 405", {"cost_usd": 0.03})) as rv:
            reason, recs = route.check_attempt(ck, p, CLAUDE, TIERS_YAML)
        self.assertIn("misses the 405", reason)
        self.assertIn("+two", rv.call_args.args[1])  # the reviewer sees the diff
        self.assertEqual(recs[-1]["cost_usd"], 0.03)
        with mock.patch.object(route, "review", return_value=(None, "review unavailable", {"cost_usd": None})):
            self.assertIsNone(route.check_attempt(ck, p, CLAUDE, TIERS_YAML)[0])  # an outage doesn't block

    def test_review_policy(self):
        mech = route.profile("mechanical", None, CLAUDE, TIERS_YAML)
        std = route.profile("standard", None, CLAUDE, TIERS_YAML)
        self.assertTrue(route.wants_review("auto", mech, None))
        self.assertFalse(route.wants_review("auto", std, None))
        self.assertTrue(route.wants_review("auto", std, "auth"))
        self.assertFalse(route.wants_review("never", mech, "auth"))
        self.assertEqual(route.reviewer_profile(mech, None, "deep", CLAUDE, TIERS_YAML)["tier"], "standard")
        self.assertEqual(route.reviewer_profile(mech, "auth", "deep", CLAUDE, TIERS_YAML)["tier"], "deep")
        self.assertEqual(route.reviewer_profile(mech, "auth", "standard", CLAUDE, TIERS_YAML)["tier"], "standard")

    def test_failed_check_resumes_one_tier_up(self):
        p = route.profile("mechanical", None, CLAUDE, TIERS_YAML)
        results = iter([("done", "s1", {"total_cost_usd": 0.01}), ("done", "s1", {"total_cost_usd": 0.2})])
        checks = {"root": self.root, "verify_cmd": None, "review": "never", "risk_area": None, "top": "deep",
                  "harness": "claude-code"}

        def fake_run(harness, cmd, task, log):
            if "--resume" in cmd:  # the escalated attempt edits a file
                (Path(self.root) / "a.txt").write_text("fixed\n", encoding="utf-8")
            return next(results)

        with mock.patch.object(route, "headless_run", side_effect=fake_run) as hr:
            runs, _ = route.run_headless("claude-code", p, "fix it", [], "why", "deep", CLAUDE, TIERS_YAML, 2, None,
                                         checks=checks)
        self.assertEqual([r["profile"]["tier"] for r in runs], ["mechanical", "standard"])
        self.assertEqual(runs[0]["checks"][0]["kind"], "diff")
        self.assertIn("changed no files", hr.call_args_list[1].args[2])
        self.assertEqual(runs[1]["checks"], [])

    def test_note_announces_checks(self):
        p = route.profile("mechanical", None, CLAUDE, TIERS_YAML)
        n = route.note(p, "why", None, False, {"verify_cmd": "npm test", "review": "auto", "risk_area": None})
        self.assertIn("`npm test`", n)
        self.assertIn("reviews the diff", n)


class Commands(unittest.TestCase):
    p = {"tier": "standard", "model": "sonnet", "effort": "medium"}

    def test_claude_interactive_puts_task_before_passthrough(self):
        cmd = route.launch_cmd("claude-code", self.p, "fix it", ["--allowedTools", "Read", "Edit"], "note", False)
        self.assertEqual(cmd[:2], ["claude", "fix it"])
        self.assertEqual(cmd[-3:], ["--allowedTools", "Read", "Edit"])

    def test_claude_headless_and_resume(self):
        cmd = route.launch_cmd("claude-code", self.p, "fix it", [], "note", True, resume="abc")
        self.assertIn("-p", cmd)
        self.assertNotIn("fix it", cmd)  # headless reads the task from stdin
        self.assertEqual(cmd[cmd.index("--resume") + 1], "abc")
        self.assertEqual(cmd[cmd.index("--output-format") + 1], "stream-json")

    def test_codex_headless(self):
        p = {"tier": "standard", "model": "gpt-6.1-sol", "effort": "medium"}
        cmd = route.launch_cmd("codex", p, "fix it", [], "note", True, resume="abc")
        self.assertEqual(cmd[:4], ["codex", "exec", "resume", "abc"])
        self.assertIn('model="gpt-6.1-sol"', cmd)
        self.assertIn("model_reasoning_effort=medium", cmd)
        self.assertEqual(cmd[-1], "-")

    def test_no_effort_flag_when_the_map_has_none(self):
        p = {"tier": "mechanical", "model": "haiku", "effort": None}
        self.assertNotIn("--effort", route.launch_cmd("claude-code", p, "x", [], "n", True))


class Classifier(unittest.TestCase):
    def call(self, **run_kwargs):
        with mock.patch.object(route, "run", **run_kwargs):
            return route.classify("task", {}, "claude-code", CLAUDE, "tiers")

    def test_structured_output(self):
        out = json.dumps({"structured_output": {"tier": "deep", "effort": "high", "risk_area": "auth", "why": "w"},
                          "total_cost_usd": 0.001})
        done = subprocess.CompletedProcess([], 0, stdout=out, stderr="")
        decision, info = self.call(return_value=done)
        self.assertEqual(decision["tier"], "deep")
        self.assertEqual(info["cost_usd"], 0.001)

    def test_failures_raise_classifier_error(self):
        cases = {
            "missing cli": {"side_effect": FileNotFoundError()},
            "timeout": {"side_effect": subprocess.TimeoutExpired("claude", 300)},
            "not json": {"return_value": subprocess.CompletedProcess([], 1, stdout="Not logged in", stderr="")},
            "bad tier": {"return_value": subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({"structured_output": {"tier": "huge"}}), stderr="")},
        }
        for name, kwargs in cases.items():
            with self.subTest(case=name), self.assertRaises(route.ClassifierError):
                self.call(**kwargs)


class Split(unittest.TestCase):
    def part(self, tier="standard", text="Fix the bug."):
        return {"title": "t", "text": text, "tier": tier, "effort": "medium", "risk_area": None, "why": "w"}

    def test_parts_are_all_or_nothing(self):
        base = {"tier": "deep", "why": "w"}
        two = route.validate({**base, "parts": [self.part(), self.part("deep")], "shared": "Do not commit."})
        self.assertEqual(len(two["parts"]), 2)
        self.assertEqual(route.validate({**base, "parts": [self.part()]})["parts"], [])  # one part: no split
        bad = route.validate({**base, "parts": [self.part(), self.part("huge")]})
        self.assertEqual(bad["parts"], [])
        empty = route.validate({**base, "parts": [self.part(), self.part(text=" ")]})
        self.assertEqual(empty["parts"], [])
        self.assertEqual(route.validate(base)["shared"], "")

    def test_part_prompt(self):
        prompt = route.part_prompt(self.part(text="Fix csrf."), "Run the tests.", 2, 3)
        self.assertTrue(prompt.startswith("This is part 2 of 3"))
        self.assertIn("Fix csrf.", prompt)
        self.assertTrue(prompt.endswith("Run the tests."))
        self.assertNotIn(3 * chr(10), route.part_prompt(self.part(), "", 1, 2))  # no empty shared block


class Misc(unittest.TestCase):
    def test_cost_line(self):
        runs = [{"profile": {"tier": "mechanical", "model": "haiku"}, "cost_usd": 0.05},
                {"profile": {"tier": "standard", "model": "sonnet"}, "cost_usd": 0.12}]
        line = route.cost_line({"cost_usd": 0.0003}, runs)
        self.assertIn("mechanical (haiku) $0.05 → standard (sonnet) $0.12", line)
        self.assertIn("total $0.17", line)
        runs[0]["checks"] = [{"kind": "review", "cost_usd": 0.03}]
        self.assertIn("reviews $0.03 · total $0.20", route.cost_line({"cost_usd": 0.0003}, runs))

    def test_resumed_run_reports_only_its_own_usage(self):
        first = {"total_cost_usd": 0.2, "modelUsage": {"haiku": {"inputTokens": 10, "costUSD": 0.2}}}
        second = {"total_cost_usd": 1.9, "modelUsage": {"haiku": {"inputTokens": 10, "costUSD": 0.2},
                                                        "sonnet": {"inputTokens": 30, "costUSD": 1.7}}}
        cost, usage = route.own_usage(second, first)
        self.assertAlmostEqual(cost, 1.7)
        self.assertEqual(list(usage), ["sonnet"])
        self.assertEqual(route.own_usage(first, None), (0.2, first["modelUsage"]))

    def test_read_task_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "issue.md"
            f.write_text("Fix the bug.\nDetails.", encoding="utf-8")
            args = mock.Mock(file=str(f), task=None)
            self.assertEqual(route.read_task(args), "Fix the bug.\nDetails.")


if __name__ == "__main__":
    unittest.main()
