# Changelog

All notable changes to this project are documented here.

## Unreleased

## 0.2.0 — 2026-10-17

- `right-size-setup` skill (user-invoked): generates `right-size-scout`, `-mechanical`, `-standard` and `-deep` subagents for Claude Code and Codex from the harness maps, asks before overwriting, and warns about Cursor reading those folders.
- `right-size`: replies are now the decision block plus at most three bullets.
- `right-size`: read-only lookups that a grep can answer stay inline; `scout` is for large reading jobs.
- Release workflow: each `v*` tag publishes `right-size-vX.Y.Z.zip` (both skills) and `right-size.skill` (Claude.ai upload).

## 0.1.0 — 2026-10-17

- `right-size` advisor skill: delegate-or-not decision, five tiers, risk floor, escalation ladder and per-project ceiling.
- Harness maps for Claude Code, Codex and Antigravity, verified against official docs on 2026-10-17.
- Plugin manifests for Claude Code and Codex marketplaces.
