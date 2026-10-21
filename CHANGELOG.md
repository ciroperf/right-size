# Changelog

All notable changes to this project are documented here.

## Unreleased

The first v1 runs showed that sessions never ask to escalate on their own: a failing session stops with a wrong answer at every tier. This release makes the router check the work itself.

### Added

- **`/right-size-audit`** (user-invoked): prices the project's Claude Code transcripts at list price and reports spend by model, token kind and subagent, model switches inside conversations, top-tier sessions that barely edited, and unpriced models, then recommends at most two changes. Local files only, no model calls. Also `scripts/audit.py` with `--days`, `--project`, `--all`, `--json`.
- **Checks in router mode** (`--print`): after each attempt the router fails it on an empty diff, on a failing `--verify-cmd`, or when a review one tier up rejects the diff (always `deep` for risk areas). `--review auto|always|never`, `--no-checks` for the old behavior.
- **Probing reviews:** the reviewer may write and run a throwaway test; the working tree is restored afterwards.
- `--max-escalations` (default 3), `--log <dir>` to keep each attempt's transcript.
- List prices per model in `harnesses/claude-code.yaml`, with source and date.

### Changed

- **The router starts on a ladder by default**: `mechanical` when checks and tests can catch a miss, `standard` otherwise. The classifier is opt-in with `--classify` (it solved the same tasks as the ladder at about three times the cost); `--split` implies it.
- **A model change starts a fresh session** with a brief (task, current diff, failure reason) instead of resuming: the bigger model re-reading the whole conversation uncached was most of an escalation's cost. Effort-only changes still resume.
- **Risk floor:** risk areas are sized like any change and reviewed at `deep`; they start at `deep` only without tests or for a design change. Breaking changes to public APIs count as a risk area, adding a capability does not.
- Bug fixes with a clear reproduction in a repo with tests start at `mechanical`.
- Sessions are told to run the existing tests of every module they changed and to delete scratch files before stopping.

### Benchmark

- **v1 with checks** (11 tasks, one run): <!-- TODO(0.4.0): final numbers after the trie rerun -->.
- **v2-hard** (<!-- TODO(0.4.0): N --> multi-module tasks Haiku fails): <!-- TODO(0.4.0) -->.
- Runner: more read-only shell tools allowed, checks for environment errors at checkout and scoring.
- Task prompts corrected where they left out behavior the PR tests check (`trie-suffix-wildcard`, `method-not-allowed`, `cache-query`, `regexp-router-unsupported`, `jsx-array`); superseded results are kept apart and don't count.

## 0.3.0 - 2026-10-18

The benchmark showed where the savings are: the model a session starts on, not delegation. This release acts on that.

### Added

- **`/right-size-defaults`** (user-invoked): recommends the project's default session model and effort from its safety net and risk profile (the standard tier at medium, or the deep tier at medium when risk dominates or tests are missing; never high or above) and, on confirmation, writes `model`/`effortLevel` (Claude Code) or `model`/`model_reasoning_effort` (Codex) at project level.
- **Router mode**, `skills/right-size/scripts/route.py`: one classifier call on the scout model sizes the task, then Claude Code or Codex starts on the tier's model and effort. Headless runs escalate on request by resuming the session one or two tiers up, print a per-step cost line, and fall back to `standard` if the classifier can't run. Supports `--file`/stdin, `--dry-run`, `--tier` and `--split` (one session per independent part; measured as more expensive, so opt-in). Standard library only. The Codex path isn't tested end to end yet.
- Advice-only harness maps for **Cursor** and **Copilot**, checked against their docs. No Gemini CLI map: it was replaced by Antigravity CLI in June 2026.
- Unit tests (router, harness maps, skill folders; no model calls) and CI on Ubuntu and Windows, Python 3.9 and 3.13.

### Changed

- **`deep` starts at medium effort** (Claude Code: Opus at medium), with high as the first escalation step at the top tier, in the advisor, `tiers.yaml` and the router. Opus at medium solved every risk-floor task in the benchmark; high cost more without solving more. Codex and Antigravity keep high until measured there.
- The advisor prints its decision block first, suggests `/model` and `/effort` for inline work on a fresh session (and only `/effort` later, which keeps the cache on current models), and keeps model names out of its text.
- The `haiku` alias resolves to Claude Haiku 5.5, so scout and mechanical run at `low` effort.
- README: per-project installs for every harness, measured results up front, the three ways to use right-size.

### Fixed

- A skill's `model` frontmatter didn't switch the main session's model in Claude Code 2.1.302 (headless or interactive), so right-size doesn't rely on it.
- A Claude Code map line that YAML parsed as a mapping, and a mis-encoded dash in the plugin description.

### Benchmark

- **v0** (10 Hono fixes merged after the training cutoff): `default` 10/10 for $3.31, `max` 10/10 for $13.01, `right-size` 9/10 for $3.77, no delegation.
- **Batches** (2 prompts × 3 independent bugs): Sonnet session 6/6 for $0.41, `default` $1.03, split $1.29, advisor $1.32, router at Opus high $1.48, forced delegation $2.09.
- **v1 prepared, not run**: Opus-high and always-Sonnet references, `--reps`, the `v1` task set with four new hard tasks.

## 0.2.0 - 2026-10-17

- `right-size-setup` skill (user-invoked): generates `right-size-scout`, `-mechanical`, `-standard` and `-deep` subagents for Claude Code and Codex from the harness maps, asks before overwriting, and warns about Cursor reading those folders.
- `right-size`: replies are now the decision block plus at most three bullets.
- `right-size`: read-only lookups that a grep can answer stay inline; `scout` is for large reading jobs.
- Release workflow: each `v*` tag publishes `right-size-vX.Y.Z.zip` (both skills) and `right-size.skill` (Claude.ai upload).

## 0.1.0 - 2026-10-17

- `right-size` advisor skill: delegate-or-not decision, five tiers, risk floor, escalation ladder and per-project ceiling.
- Harness maps for Claude Code, Codex and Antigravity, verified against official docs on 2026-10-17.
- Plugin manifests for Claude Code and Codex marketplaces.
