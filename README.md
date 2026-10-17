<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/banner-light.svg">
  <img alt="right-size: give every coding task the compute it deserves" src="assets/banner-light.svg" width="100%">
</picture>

<br/>

**An Agent Skill that decides whether a coding task deserves a subagent, which tier, and which reasoning effort — then applies it in your harness.**

[![License: MIT](https://img.shields.io/badge/license-MIT-0d9488.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-SKILL.md-7c3aed.svg)](https://agentskills.io)
[![Release](https://img.shields.io/github/v/release/ciroperf/right-size?color=blue)](https://github.com/ciroperf/right-size/releases/latest)
[![Status](https://img.shields.io/badge/status-beta-orange.svg)](#roadmap)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[![Claude Code](https://img.shields.io/badge/Claude%20Code-supported-D97757?logo=claude&logoColor=white)](#install)
[![Codex](https://img.shields.io/badge/Codex-supported-111111)](#install)
[![Antigravity](https://img.shields.io/badge/Antigravity-advice-4285F4?logo=google&logoColor=white)](#harness-support)
[![Cursor](https://img.shields.io/badge/Cursor-planned-555555)](#harness-support)
[![Copilot](https://img.shields.io/badge/Copilot-planned-555555?logo=githubcopilot&logoColor=white)](#harness-support)
[![Gemini CLI](https://img.shields.io/badge/Gemini%20CLI-planned-555555?logo=googlegemini&logoColor=white)](#harness-support)

[Install](#install) · [Usage](#usage) · [How it works](#how-it-works) · [Tiers](#tiers) · [Harness support](#harness-support) · [Benchmark](#benchmark) · [FAQ](#faq)

</div>

---

## Why

Coding agents waste tokens in two predictable ways:

1. **Everything runs on the biggest model at the highest effort**, including renames and one-line fixes.
2. **Work gets delegated to subagents when doing it inline would be cheaper.** A subagent starts cold: its own system prompt, its own context, re-reading files the main agent already has.

`right-size` sizes the task first, then picks the smallest setup that still gets it done, and tells you when to step up.

```
right-size: delegate=no · tier=deep · effort=high
why: auth + users schema change (risk floor → deep), no tests, ~3 files
apply: inline; run the session on opus (/model opus) with /effort high (claude-code)
escalate if: deep attempt fails → fable/xhigh, only after you confirm
```

**What makes it different**

- 🧭 **It can say "don't delegate".** Inline is the default; a subagent has to earn its start-up cost.
- 🔌 **Multi-harness.** One decision, translated into each agent's native config: Claude Code, Codex, Antigravity, with more on the way.
- 🛡️ **Risk-aware, not keyword-based.** Auth, payments, migrations and public APIs start at the top tier, however small the diff. Read-only questions about them stay cheap.
- 📈 **Escalates on evidence.** Start low when tests exist; step up one tier on a verifiable failure, two on a reasoning failure.
- 📏 **Measured, not claimed.** A reproducible benchmark is part of the repo, including the cases where right-size makes things worse.

## Install

Install it for **every project** (global) or **just one project**. A project install lives in the repo, so you can try right-size on one codebase, or share it with your team, without touching anything else.

<details open>
<summary><strong>Claude Code</strong></summary>

Global, for all your projects:

```bash
claude plugin marketplace add ciroperf/right-size
claude plugin install right-size@ciroperf
```

Just this project, shared with the team through `.claude/settings.json` (teammates are offered the plugin when they open the repo):

```bash
claude plugin marketplace add ciroperf/right-size --scope project
claude plugin install right-size@ciroperf --scope project
```

Use `--scope local` instead for this project only, without committing anything.

</details>

<details>
<summary><strong>Codex</strong></summary>

Global, as a plugin that updates itself:

```bash
codex plugin marketplace add ciroperf/right-size
codex plugin add right-size@ciroperf
```

Just this project: Codex plugins are always user-wide, so copy the skills into the repo's `.agents/skills/` instead:

```bash
npx skills@latest add ciroperf/right-size -a codex
```

</details>

<details>
<summary><strong>Antigravity, Cursor, Copilot, Gemini CLI and others</strong> (manual updates)</summary>

Just this project (the default when run inside a repo):

```bash
npx skills@latest add ciroperf/right-size
```

Global: add `-g`. Pick agents with `-a`, e.g. `-a cursor`. Update later with `npx skills update`.

</details>

<details>
<summary><strong>Claude.ai or manual install</strong></summary>

Download from the [latest release](https://github.com/ciroperf/right-size/releases/latest):

- `right-size.skill`: upload it in Claude.ai under **Settings → Capabilities → Skills**.
- `right-size-vX.Y.Z.zip`: both skills. Copy the `skills/` folders into your agent's skills directory (for example `.claude/skills/` or `.agents/skills/`), keeping them side by side.

</details>

### Optional: generate the subagents

```text
> /right-size-setup
```

This writes one subagent per tier with model and effort preset: `.claude/agents/right-size-*.md` in Claude Code, `.codex/agents/right_size_*.toml` in Codex. It asks before overwriting anything. Without these agents right-size still works, but it can only pass a model per call, and effort then follows the session.

## Usage

It runs on its own when an agent is about to delegate, plan multi-step work, or pick a model. You can also ask for it directly:

```text
> right-size this before you start
> is this worth a subagent?
> size these four tickets
```

Each answer is a four-line block: the decision, the facts behind it, how to apply it in the harness you're in, and when to step up. At most three short notes follow, only for assumptions to confirm or things the subagent's brief must include.

<details>
<summary><strong>Example: a rename across a monorepo (Claude Code)</strong></summary>

```
right-size: delegate=yes · tier=mechanical · effort=low
why: 14 call sites in 9 unopened files, a one-sentence rename pattern, tsc --noEmit + vitest catch misses
apply: right-size-mechanical (haiku), or general-purpose with model=haiku if that agent doesn't exist (claude-code)
escalate if: tsc or vitest still red after a real attempt → standard (sonnet, medium)
```

</details>

<details>
<summary><strong>Example: a read-only question about payment code (Codex)</strong></summary>

```
right-size: delegate=no · tier=inline · effort=session
why: read-only (so payments doesn't push it to deep), likely 1-3 files once grep finds the entry point
apply: inline; keep session model and effort (codex)
escalate if: event handling fans out past ~10 files / ~2k lines → spawn right_size_scout (gpt-6-luna, effort low, read-only)
```

</details>

<details>
<summary><strong>Example: sizing a batch of tickets before fanning out</strong></summary>

```
1. right-size: delegate=no  · tier=inline   · effort=session   why: one line in list_display, field already exists
2. right-size: delegate=yes · tier=deep     · effort=high      why: float→Decimal data migration on a money column
3. right-size: delegate=yes · tier=standard · effort=medium    why: mechanical pattern, but scripts/ has no tests
4. right-size: delegate=yes · tier=standard · effort=medium    why: new view + button on an existing pattern
escalate if: tests red after a real attempt → one tier up; wrong approach → two tiers up
```

</details>

> The examples are real outputs from the skill's test suite (Claude Opus 5.5, October 2026), lightly trimmed.

## How it works

```mermaid
flowchart LR
    A[Task] --> B{Size it<br/>files · safety net · risk · reading vs reasoning}
    B --> C{Worth a subagent?}
    C -- no --> D[inline]
    C -- yes --> E{Pick tier}
    E --> F[scout]
    E --> G[mechanical]
    E --> H[standard]
    E --> I[deep]
    D & F & G & H & I --> J[Pick effort<br/>raise effort before model]
    J --> K[Apply ceiling<br/>.right-size.yaml]
    K --> L[Translate to harness<br/>model + effort]
```

The decision itself is kept cheap: it uses what's already in context plus at most a couple of quick lookups. Sizing a task should never cost more than the savings it's after.

## Tiers

Model names live only in the harness maps. The skill reasons in abstract tiers:

| Tier | For | Claude Code | Codex | Antigravity |
|---|---|---|---|---|
| `inline` | Small changes, files already in context | session model | session model | session model |
| `scout` | Read and search only | `haiku` | `gpt-6-luna` · low | Flash · Low |
| `mechanical` | Renames, boilerplate, import updates | `haiku` | `gpt-6-luna` · low | Flash · Low |
| `standard` | Ordinary features and fixes | `sonnet` · medium | `gpt-6.1-sol` · medium | Flash · High |
| `deep` | Auth, security, migrations, payments, concurrency | `opus` · high | `gpt-6-astra` · high | Pro · High |

Mappings were verified against each vendor's docs on 2026-10-17 and are not yet benchmarked. They live in [`skills/right-size/harnesses/`](skills/right-size/harnesses/), and keeping them current is most of this project's maintenance.

## Harness support

| Level | Harnesses | What you get |
|---|---|---|
| **Full** | Claude Code, Codex | Advice, native config, benchmark |
| **Config** *(planned)* | Cursor, Copilot, Gemini CLI, Antigravity | Advice, native subagent config, smoke test |
| **Advice** | Any harness that loads Agent Skills | Advice in tier terms |

## Configuration

Cap the tier for a project by adding `.right-size.yaml` at the repo root:

```yaml
max_tier: standard   # anything above asks for confirmation first
```

## When not to use subagents

Delegation costs more than it saves when:

- the files are already in the main context;
- the change is a few lines;
- the brief would be about as long as the work;
- you are iterating on the change interactively;
- the "parallel" parts actually depend on each other.

## Benchmark

> 🚧 **In progress.** No savings figure will appear here until it's measured.

The plan: 15–20 real tasks across 2–3 public repos, run in Claude Code and Codex under three setups (harness default, always the top model at high effort, right-size). We'll track total tokens (input, output, cache), wall time, list-price cost, and whether each task was solved, judged by tests or a checklist. Scripts and dated results will live in [`bench/`](bench/), regressions included.

## FAQ

<details>
<summary><strong>Does it replace a model router or proxy?</strong></summary>

No. It works at the agent level, with the subagents and settings your harness already has. API-level routers such as claude-code-router or OpenRouter are complementary.

</details>

<details>
<summary><strong>How is this different from other routing skills?</strong></summary>

Some skills advise a tier and effort but leave the rest to you. Others hook every subagent spawn in a single harness. right-size also decides *whether* to delegate, maps the decision to native config in several harnesses, and backs it with a public benchmark.

</details>

<details>
<summary><strong>Will it go stale when new models ship?</strong></summary>

The skill reasons in tiers, so only the YAML maps need updating. Each map records the date it was verified.

</details>

## Roadmap

- [x] Advisor skill with tiers, risk floor and escalation
- [x] Harness maps for Claude Code, Codex and Antigravity
- [x] `right-size-setup`: generate native subagents (`scout`, `mechanical`, `standard`, `deep`) for Claude Code and Codex
- [ ] Benchmark v0: one repo, one harness
- [ ] Cursor, Copilot and Gemini CLI maps with smoke tests
- [ ] Benchmark v1: Claude Code + Codex, published results

## Contributing

Model updates, new harness maps and benchmark tasks are all welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © Ciro Perfetto
