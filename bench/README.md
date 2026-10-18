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
| `router` | picked per task | picked per task | [`route.py`](../skills/right-size/scripts/route.py) sizes the task first and starts the session on the tier's model and effort; headless escalation on request. Added after v0, not in the v0 results |

Claude Code's default effort on Opus 5.5 is `medium`.

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

## Results

- [`results/2026-10-17-v0/`](results/2026-10-17-v0/): 10 tasks × `default`, `max`, `right-size`. See [`summary.md`](results/2026-10-17-v0/summary.md) and the [README](../README.md#benchmark) for the reading.

- [`results/2026-10-18-batch/`](results/2026-10-18-batch/): two batches of three independent Hono fixes in one prompt, `default` vs `right-size`, plus `delegate`, an experiment that forces every part onto the right-size subagent for its tier. All solved 2/2. Totals: `default` $1.03, `right-size` $1.32 (it chose not to delegate), `delegate` $2.09. Haiku and Sonnet subagents were cheap, but the Opus orchestrator's briefing and review, plus security parts sent to the `deep` subagent on Opus at high effort, cost more than doing everything inline. `router` also solved 2/2 for $1.48: each batch contained one security fix, so the risk floor put the whole session on `deep` (Opus at high effort), above Claude Code's default of medium. `router-standard`, the router pinned to `standard` (the whole session on Sonnet at medium effort), solved 2/2 for $0.41, 60% below the default and about three times faster. `router-split` ran each bug as its own session on its own tier (deep parts on Opus at medium, the rest on Sonnet): 2/2 for $1.29, above the default, because each session pays its own start-up and the Opus parts alone cost about as much as the default's whole batch.

## Limits

- One run per task and configuration: no variance estimate yet.
- One repo, one harness, a handful of tasks. Read the numbers as a first signal, not a verdict.
- The `right-size` configuration includes the advisor's own overhead (reading the skill), which is the honest comparison.
