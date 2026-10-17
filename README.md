# right-size

> **Status: work in progress.** Nothing to install yet.

Agent Skills that decide how much compute a coding task deserves — **whether to delegate to a subagent, at which tier, and with which reasoning effort** — and translate that decision into each harness's native config.

The goal is the lowest cost and latency **at the same number of tasks solved**, backed by a reproducible benchmark rather than claims.

## Planned harness support

| Level | Harnesses | What ships |
|---|---|---|
| Full | Claude Code, Codex | Advisor skill, generated subagent config, benchmark |
| Config | Cursor, Copilot, Gemini CLI, Antigravity | Advisor skill, generated subagent config, smoke test |
| Advice | Any harness supporting Agent Skills | Advisor skill with text-only recommendations |

## Tiers

| Tier | For |
|---|---|
| `inline` | Don't delegate: the main agent does it |
| `scout` | Read and search only |
| `mechanical` | Predictable transforms (renames, boilerplate) |
| `standard` | Ordinary features and fixes |
| `deep` | High risk or long reasoning (security, auth, migrations, concurrency) |

## Benchmark

Coming soon. Results — including cases where right-size makes things worse — will be published in [`bench/results/`](bench/results/).

## License

[MIT](LICENSE)
