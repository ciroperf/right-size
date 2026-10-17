# Benchmark

Does right-size save tokens without losing solved tasks? This folder holds the tasks, the runner and the results.

## Method (v0)

- **Repo:** [honojs/hono](https://github.com/honojs/hono), TypeScript, ~26k lines of source, vitest.
- **Tasks:** real PRs merged after 2026-07-01, so after the training cutoff of the models under test. A model can't have memorized the fix. See [`tasks/hono.yaml`](tasks/hono.yaml).
- **Prompt:** the observable bug, written like an issue. It never points to the fix.
- **Scoring:** after the agent finishes, the PR's own test files are copied in, overwriting any edits the agent made to them, and run. Solved means they pass. Before running, `validate` checks that every task's tests fail on the commit before the PR and pass on the PR itself.
- **Harness:** Claude Code in headless mode (`claude -p`), same version for all runs. Project settings only, no MCP servers. The same tool allowlist for every run (file tools, subagents, skills, the test command and read-only git).
- **Metrics:** tokens per model (input, output, cache read, cache write), list-price cost as reported by Claude Code, wall time, number of turns and subagents. Cost is computed at list price whatever the billing plan.

### Configurations

| Name | Main model | Effort | right-size |
|---|---|---|---|
| `default` | Opus 5.5 | Claude Code default | no |
| `max` | Opus 5.5 | `max` | no |
| `right-size` | Opus 5.5 | Claude Code default | skill + generated subagents, plus a one-line instruction to size the task first |

Fable 5.1, the top model, needs extra usage credits on the subscription used for these runs, so `max` uses Opus at the highest effort instead.

## Running it

```bash
git clone https://github.com/honojs/hono bench/work/hono   # full history needed
cd bench/work/hono && npx -y bun@1.2.20 install --frozen-lockfile && cd -
python bench/run.py validate
python bench/run.py run --out bench/results/<date>-v0
python bench/run.py summarize bench/results/<date>-v0
```

Raw transcripts and diffs go to `bench/raw/` (not committed). Per-run records and `summary.md` go to `bench/results/`.

## Limits

- One run per task and configuration: no variance estimate yet.
- One repo, one harness, a handful of tasks. Read the numbers as a first signal, not a verdict.
- The `right-size` configuration includes the advisor's own overhead (reading the skill), which is the honest comparison.
