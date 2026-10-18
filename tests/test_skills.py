"""Every skill folder is complete and registered everywhere it ships. No model calls."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())


class Skills(unittest.TestCase):
    def test_folders_are_complete(self):
        for d in SKILLS:
            with self.subTest(skill=d.name):
                text = (d / "SKILL.md").read_text(encoding="utf-8")
                self.assertRegex(text, rf"(?m)^name: {re.escape(d.name)}$")
                self.assertRegex(text, r"(?m)^description: \S")
                self.assertTrue((d / "agents" / "openai.yaml").exists(), "Codex metadata missing")

    def test_registered_in_plugin_and_release(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        for d in SKILLS:
            with self.subTest(skill=d.name):
                self.assertIn(f"./skills/{d.name}", plugin["skills"])
                self.assertIn(f"skills/{d.name}", release)

    def test_user_invoked_skills_stay_explicit(self):
        for d in SKILLS:
            text = (d / "SKILL.md").read_text(encoding="utf-8")
            if "disable-model-invocation: true" in text:
                with self.subTest(skill=d.name):
                    meta = (d / "agents" / "openai.yaml").read_text(encoding="utf-8")
                    self.assertIn("allow_implicit_invocation: false", meta)

    def test_no_model_names_in_skill_text(self):
        # Model names belong in harnesses/*.yaml only.
        names = re.compile(r"\b(haiku|sonnet|opus|fable|gpt-\d|gemini-\d|composer-\d)\b", re.I)
        for d in SKILLS:
            with self.subTest(skill=d.name):
                self.assertIsNone(names.search((d / "SKILL.md").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
