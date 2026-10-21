---
name: right-size-defaults
description: Recommend the default model and reasoning effort for new sessions in this project, explain why, and on confirmation write it to the project's harness settings.
disable-model-invocation: true
---

Most of the saving right-size has measured comes from the session's default, not from per-task tricks: starting on a cheaper model at medium effort solved the same tasks for a fraction of the cost, while maximum effort cost several times more and solved nothing extra. This skill picks that default for the current project, so every new session starts there and escalates only when a task needs it.

Keep the check cheap: a file listing, a look at the README and the test setup. Don't read source code in depth.

## Steps

1. **Pick the harness.** Use the one you're running in unless the user named another. Claude Code and Codex get a settings change; Antigravity, Cursor and Copilot get advice only, because right-size doesn't write their settings yet. For any other harness, give the advice in tier terms.

2. **Load the maps.** Read `../right-size/tiers.yaml` and `../right-size/harnesses/<harness>.yaml`, next to this skill's folder. If they're missing, the `right-size` skill isn't installed alongside this one: tell the user to install it and stop.

3. **Check the project.**
   - Safety net: test files, a test script, a typecheck, CI that runs them.
   - Risk: is most of the code in a `risk_floor` area from `tiers.yaml` (an auth service, a payments system, a crypto library, a migrations tool)? A few risky modules in an ordinary app don't count; per-task escalation handles those.

4. **Choose the default profile.**
   - Safety net present → the `standard` tier's model at `medium` effort, even when risk is dominant: risky changes get a `deep`-tier review per task instead of a bigger model for everything.
   - No safety net → the `deep` tier's model at `medium` effort.
   - Never recommend `high`, `xhigh` or `max` as a default. They are escalation steps: use them when a task has failed after a real attempt.

5. **Report** in this shape, then the escalation advice, and nothing longer:

   ```
   right-size defaults: model=<model> · effort=medium (<harness>)
   why: <two or three facts from step 3>
   escalate: after a real failed attempt, switch the model with /model <deep tier model>; at the top, raise effort to high
   evidence: https://github.com/ciroperf/right-size/tree/main/bench
   ```

   Mention that effort changes keep the prompt cache on current models, so `/effort` is cheap at any point, while a model switch re-reads the conversation once without cache.

6. **Offer to write it** (Claude Code and Codex only). Ask first, and show the exact change.
   - Claude Code: set `model` and `effortLevel` in `.claude/settings.local.json` (only this user; the default to offer) or `.claude/settings.json` (shared with the team). Merge into the existing JSON and touch no other key. Don't use `~/.claude/settings.json`: there, current models ignore a top-level `effortLevel`.
   - Codex: set `model` and `model_reasoning_effort` in the project's `.codex/config.toml`, touching no other key. Codex loads it only for trusted projects; say so.
   - If either key is already set to something else, show the current value and ask before replacing it.

7. **Check for overrides.** If `ANTHROPIC_MODEL` or `CLAUDE_CODE_EFFORT_LEVEL` is set in the environment, or a `--model` or `--effort` flag is used to launch sessions, say that it overrides the settings file.
