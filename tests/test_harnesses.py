"""Validation of the harness maps in skills/right-size/harnesses/. No model calls.

These check structure only. Whether a harness actually runs a subagent on the
mapped model needs a live smoke test, which these are not.

Run: python -m unittest discover -s tests -v
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "right-size"
sys.path.insert(0, str(SKILL / "scripts"))

import route  # noqa: E402

HARNESSES = ["claude-code", "codex", "antigravity", "cursor", "copilot"]
TIERS = ["inline", "scout", "mechanical", "standard", "deep"]
MAPS = sorted((SKILL / "harnesses").glob("*.yaml"))


class HarnessMaps(unittest.TestCase):
    def test_expected_maps_exist(self):
        self.assertEqual(sorted(f.stem for f in MAPS), sorted(HARNESSES))

    def test_skill_lists_every_map(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for name in HARNESSES:
            with self.subTest(harness=name):
                self.assertIn(f"`{name}`", skill)

    def test_metadata(self):
        for f in MAPS:
            with self.subTest(harness=f.stem):
                data = route.read_yaml(f)
                self.assertEqual(data.get("harness"), f.stem)
                self.assertRegex(str(data.get("verified")), r"^\d{4}-\d{2}-\d{2}$")
                self.assertRegex(f.read_text(encoding="utf-8"), r"https://", "cite the docs checked")
                steps = data.get("how_to_apply")
                self.assertIsInstance(steps, list)
                self.assertTrue(steps and all(isinstance(s, str) for s in steps))

    def test_tiers(self):
        for f in MAPS:
            data = route.read_yaml(f)
            for tier in TIERS:
                with self.subTest(harness=f.stem, tier=tier):
                    entry = data["tiers"][tier]
                    if tier == "inline":
                        self.assertTrue(entry.get("apply"))
                    else:
                        self.assertTrue(str(entry.get("model") or "").strip())
            with self.subTest(harness=f.stem, check="scout read-only"):
                self.assertEqual(data["tiers"]["scout"].get("tools"), "read-only")


if __name__ == "__main__":
    unittest.main()
