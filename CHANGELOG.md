# Changelog

All notable changes to this project are documented here.

## Unreleased

- README: per-project install for every harness (Claude Code `--scope project|local`, Codex and others via `npx skills` into the repo).
- Claude Code map: the `haiku` alias now resolves to Claude Haiku 5.5, which takes an effort level; scout and mechanical run at `low`.
- Benchmark v0 harness: runner, task set from post-cutoff Hono PRs, method in `bench/README.md`.
- Router mode: `skills/right-size/scripts/route.py` sizes a task with one classifier call on the scout model, launches Claude Code or Codex on the tier's model and effort, and in headless mode resumes the session one or two tiers up when it asks to escalate. Standard library only. The Codex path isn't tested end to end yet.
- `right-size`: on a fresh session, inline work suggests switching the session to the tier's model and effort. Later on it suggests effort changes only, which keep the prompt cache on the 5.5 models.
- Claude Code map: a skill's `model` frontmatter didn't switch the main session's model in Claude Code 2.1.302, so right-size doesn't rely on it.
- Bench: `router` configuration (classifier cost included in the totals).
- Router: `--file` and stdin input, fallback to `standard` when the classifier can't run, per-step cost line, exit code 1 when the session errors. The classifier call disables skills, which cut its prompt from about 6k to 1.4k tokens.
- Router: resumed sessions report cumulative totals in Claude Code, so each run's own cost and usage is now the difference from the previous run. Escalation (haiku → sonnet via `--resume`) tested live.
- Unit tests for the router (`tests/`, no model calls) and a CI workflow on Ubuntu and Windows, Python 3.9 and 3.13.
- Claude Code map: fixed a `how_to_apply` line that YAML parsed as a mapping.
- Benchmark v0 results: 10 Hono tasks. `default` solved 10/10 for $3.31, `max` 10/10 for $13.01, `right-size` 9/10 for $3.77, with no delegation. `accepts-wildcard` prompt corrected and rerun.
- `right-size`: always print the decision block first. In 8 of 10 headless bench runs the decision stayed in the model's thinking.

## 0.2.0 — 2026-10-17

- `right-size-setup` skill (user-invoked): generates `right-size-scout`, `-mechanical`, `-standard` and `-deep` subagents for Claude Code and Codex from the harness maps, asks before overwriting, and warns about Cursor reading those folders.
- `right-size`: replies are now the decision block plus at most three bullets.
- `right-size`: read-only lookups that a grep can answer stay inline; `scout` is for large reading jobs.
- Release workflow: each `v*` tag publishes `right-size-vX.Y.Z.zip` (both skills) and `right-size.skill` (Claude.ai upload).

## 0.1.0 — 2026-10-17

- `right-size` advisor skill: delegate-or-not decision, five tiers, risk floor, escalation ladder and per-project ceiling.
- Harness maps for Claude Code, Codex and Antigravity, verified against official docs on 2026-10-17.
- Plugin manifests for Claude Code and Codex marketplaces.
