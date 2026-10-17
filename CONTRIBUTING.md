# Contributing

Thanks for helping keep right-size accurate. The most useful contributions, in order:

## 1. Model and harness updates

New models ship often, and the maps in [`skills/right-size/harnesses/`](skills/right-size/harnesses/) go stale. When you update one:

- link the official doc you checked;
- bump the `verified:` date at the top of the file;
- keep model names out of `SKILL.md` and `tiers.yaml`: they belong only in the harness maps.

## 2. New harness maps

Add `skills/right-size/harnesses/<harness>.yaml` following the existing files. Include where subagents are defined, which fields set model and effort, and a `how_to_apply` section. If the harness can't set effort per agent, say so explicitly.

## 3. Benchmark tasks

Tasks for [`bench/`](bench/) must come from public repos and have an objective pass check (a test, a build, or a written checklist). Results showing right-size doing *worse* are just as welcome.

## Pull requests

- Keep everything in English.
- One topic per PR.
- Add a line to [CHANGELOG.md](CHANGELOG.md) under **Unreleased**.
