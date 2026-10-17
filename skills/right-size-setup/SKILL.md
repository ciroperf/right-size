---
name: right-size-setup
description: Generate the right-size subagents (scout, mechanical, standard, deep) for this project, with model and reasoning effort preset for the current harness.
disable-model-invocation: true
---

This creates one subagent per delegating tier, so that when the `right-size` skill says "delegate to `right-size-mechanical`", that agent already exists and runs on the right model and effort. Without them, `right-size` still works but can only pass a model per call, and effort then follows the session.

## Steps

1. **Pick the harness.** Use the one you're running in unless the user named another: `claude-code` or `codex`. For any other harness, say it isn't supported by setup yet and stop. `right-size` still gives advice there.

2. **Load the tier map.** Read `../right-size/harnesses/<harness>.yaml`, next to this skill's folder. If it's missing, the `right-size` skill isn't installed alongside this one: tell the user to install it and stop. Use only the `scout`, `mechanical`, `standard` and `deep` entries.

3. **Fill the templates** in `templates/<harness>/` from this skill's folder, one file per tier:
   - `{{model}}` → the tier's `model`.
   - `{{effort}}` (Codex) → the tier's `effort`.
   - `{{effort_line}}` (Claude Code) → `effort: <value>` plus a newline, or an empty string when the tier's effort is `null` (Haiku has no effort setting).

   Keep the rest of each template unchanged.

4. **Check before writing.** Targets:
   - Claude Code: `.claude/agents/right-size-<tier>.md`
   - Codex: `.codex/agents/right_size_<tier>.toml`

   If a target already exists and differs, show the user the difference and ask before overwriting. Never touch other files in those folders.

5. **Warn about Cursor.** If the project has a `.cursor/` folder, tell the user that Cursor also reads `.claude/agents/` and `.codex/agents/`, and may fail to resolve Claude or Codex model names. right-size doesn't generate Cursor agents yet.

6. **Offer a ceiling.** Ask whether they want to cap the tier for this project. If they do, write `.right-size.yaml` at the repo root with `max_tier: <tier>`. Skip the question if the file already exists.

7. **Report** the files written, the model and effort of each agent, and how to check them: `/agents` in Claude Code, or the agent list in Codex. Mention that the maps were verified on the date in the harness file, and that the agents can be regenerated after updating right-size.
