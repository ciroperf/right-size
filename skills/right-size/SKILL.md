---
name: right-size
description: Decide how much compute a coding task deserves before doing it — whether to delegate to a subagent or work inline, which tier (inline, scout, mechanical, standard, deep), and which reasoning effort — then apply that choice in the current harness. Use before spawning a subagent, when splitting work into tickets or parallel tasks, when the user asks which model or effort to use, whether something is worth a subagent, or how to save tokens or cost on a task. Also use when another skill is about to fan work out to subagents. Skip it for trivial one-step edits where the answer is obviously "just do it".
---

Most token waste in coding agents comes from two habits: sending everything to the biggest model at the highest effort, and delegating to subagents when doing the work inline would be cheaper. This skill picks the smallest setup that still solves the task, and says when to step up.

The decision itself must stay cheap. Use what is already in context plus at most a couple of quick lookups (a file listing, a grep). Never explore the codebase in depth just to size a task: that spends the tokens this skill exists to save.

## Steps

1. **Read the reference files.** `tiers.yaml` (next to this file) defines the tiers, risk areas, delegation rules, and escalation ladder. `harnesses/<harness>.yaml` maps tiers to the harness you are running in: `claude-code`, `codex`, `antigravity`, `cursor`, or `copilot`. For any other harness, give the decision in tier terms and say that no native mapping exists yet.

2. **Size the task.** Estimate, roughly:
   - how many files and lines will change, and how much must be read first;
   - whether a safety net exists: tests, a typecheck, a linter, a build that fails loudly;
   - whether it touches a risk area from `risk_floor`;
   - whether it is mostly reading, mostly mechanical, or mostly reasoning;
   - whether it splits into independent parts.

3. **Decide whether to delegate.** Start from inline. A subagent starts cold: it gets its own system prompt and has to re-read whatever context it needs. So delegate only when that start-up cost buys something: keeping a large amount of reading out of the main context, running independent parts in parallel, or handing off a chunk that is large compared to its brief. If the relevant files are already in context, or the next reasoning step needs the result right away, stay inline.

4. **Pick the tier.**
   - Changes in a risk area → `deep`, whatever the size.
   - Mostly reading, and a lot of it → `scout`, even in a risk area: reading can't break anything. A lookup that a grep or two can answer stays `inline`.
   - Pattern you can state in a sentence, easy to verify → `mechanical`.
   - Ordinary feature or fix → `standard`.
   - No safety net → one tier higher (not for `scout`), because failures will surface late.

5. **Pick the effort.** Start from the tier's `default_effort`. If the task is small but needs careful thought (a subtle bug, a tricky algorithm), raise effort one step before raising the tier: it needs thinking, not a bigger model.

6. **Apply the ceiling.** If `.right-size.yaml` exists at the repo root, respect its `max_tier`. Going above the cap, or past `deep` (the harness's `beyond_deep`), needs the user's confirmation: ask, don't assume.

7. **Translate and report.** Map the tier to the current harness with its `harnesses/*.yaml` file and output the block below. Then act on it, following the file's `how_to_apply`, unless the user only asked for advice.

## Output

Print the block before doing anything else, even when the decision is to stay inline and even in a non-interactive run: it is the only record of the decision.

The block below is the whole answer. `why` gives the two or three facts that drove the choice, so the user can disagree quickly. `apply` covers only the harness you are running in.

After the block, add at most three short bullets, and only for things that would change the decision (an assumption to confirm) or that the subagent's brief must include. Don't restate the reasoning in prose. An advisor that writes 400 words spends the tokens it is supposed to save.

```
right-size: delegate=no · tier=mechanical · effort=low
why: 3 files, rename only, tests present
apply: inline; keep session effort (claude-code)
escalate if: tests fail → standard/medium
```

When delegating, `apply` names the agent or model to use, e.g. `apply: right-size-scout (haiku)` or `apply: spawn with model gpt-6-luna, effort low`.

When the work stays inline and the session has barely started, the cheapest move is often to switch the session itself to the tier's model and effort. You can't switch it yourself, so say it in `apply`, e.g. `apply: inline; switch now with /model sonnet and /effort medium (session is fresh)`. Effort changes are cheap at any point on models whose cache survives them (see the harness notes). A model switch re-reads the whole conversation uncached, so suggest it only while the context is still small.

When sizing several tickets or subtasks at once (for example before fanning out an implementation plan), write one `right-size:` line per item with a short `why`, followed by a single shared `escalate if:` line when they share a rule.

## Router mode

To size a task before any session starts, `scripts/route.py` in this skill's folder makes one cheap classifier call with `tiers.yaml` and launches Claude Code or Codex on the tier's model and effort. Headless (`--print`) it also escalates on its own when the session asks for it. When the user wants that, give them the command with the script's absolute path, e.g. `python <this folder>/scripts/route.py "fix the failing date test"`.

## Escalation

After a failed attempt, step up according to `escalation` in `tiers.yaml`:
- syntax or tooling error → retry once at the same tier with the error in the brief;
- verifiable failure (tests red, build broken after a real attempt) → one tier up;
- reasoning failure (wrong approach, misread spec) → two tiers up;
- already at `deep` → raise effort one step, up to high, before anything past `deep`.

Always respect the ceiling. Report each escalation with a fresh `right-size:` line so the user can see where the cost went.

## When not to delegate

Delegation is a tool, not a default. The common cases where it costs more than it saves:
- the files are already in the main context;
- the task is a few lines;
- the subagent's brief would be about as long as the work itself;
- the user is iterating on the change interactively;
- several "parallel" parts actually depend on each other's results.
