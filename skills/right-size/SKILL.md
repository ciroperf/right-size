---
name: right-size
description: Decide how much compute a coding task deserves before doing it: whether to delegate to a subagent or work inline, which tier (inline, scout, mechanical, standard, deep) and which reasoning effort. Then apply that choice in the current harness. Use before spawning a subagent, when splitting work into tickets or parallel tasks, when the user asks which model or effort to use, whether something is worth a subagent, or how to save tokens or cost on a task. Also use when another skill is about to fan work out to subagents. Skip it for trivial one-step edits where the answer is obviously "just do it".
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

4. **Pick the tier.** Size by the structure of the change, not by its domain: how many places must change together and how many existing behaviors must keep working.
   - Mostly reading, and a lot of it → `scout`, even in a risk area: reading can't break anything. A lookup that a grep or two can answer stays `inline`.
   - Pattern you can state in a sentence, easy to verify → `mechanical`.
   - Bug fix with a clear reproduction, in a repo with tests → `mechanical`: escalate if a check fails.
   - Feature, or a fix that needs design decisions → `standard`.
   - Change that threads through several modules or must keep many behaviors intact → `deep`.
   - No safety net → one tier higher (not for `scout`), because failures will surface late.
   - Risk area: size it like anything else, but plan the verification now: tests must pass and the diff gets a review from the `deep` tier before you call it done. Without tests, or for a design change in the area (a new auth flow, a migration), start at `deep`.

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

When delegating, `apply` names the agent or model to use, with the model taken from the harness map, e.g. `apply: right-size-scout (<scout model>)` or `apply: spawn with model <scout model>, effort low`.

When the work stays inline and the session has barely started, the cheapest move is often to switch the session itself to the tier's model and effort. You can't switch it yourself, so say it in `apply`, e.g. `apply: inline; switch now with /model <standard model> and /effort medium (session is fresh)`. Effort changes are cheap at any point on models whose cache survives them (see the harness notes). A model switch re-reads the whole conversation uncached, so suggest it only while the context is still small.

When sizing several tickets or subtasks at once (for example before fanning out an implementation plan), write one `right-size:` line per item with a short `why`, followed by a single shared `escalate if:` line when they share a rule.

## Router mode

To pick the model for a whole session before it starts, `scripts/route.py` in this skill's folder launches Claude Code or Codex on a tier's model and effort. Headless (`--print`) with tests, it starts on the cheapest writing tier and checks each attempt: no file changed, `--verify-cmd` failing, or a higher-tier review (which may run throwaway probes) rejecting the diff. A failed check moves one tier up; a new model starts a fresh session with a brief instead of re-reading the old one. Interactive, or without tests, it starts on `standard`. `--classify` lets a cheap classifier pick the starting tier instead. When the user wants that, give them the command with the script's absolute path, e.g. `python <this folder>/scripts/route.py --print --verify-cmd "npm test" "fix the failing date test"`.

## Escalation

Don't trust "done" without a check: models at every tier stop with a wrong answer and believe it is right. Before calling the work finished, run the checks in `escalation.checks`: something actually changed, tests or the project's checks pass, and for risk areas or `mechanical` work a review one tier up (a short-lived reviewer subagent with the task and the diff, allowed to write and run a throwaway test for a requirement it doubts) finds no missed requirement and nothing broken. Passing tests are not enough on their own: the defects that remain are the ones the tests don't cover.

When escalating to a bigger model, hand it a fresh brief (the task, the current diff, why the last attempt failed) rather than the whole previous conversation: a new model re-reads everything uncached.

After a failed attempt or check, step up according to `escalation` in `tiers.yaml`:
- syntax or tooling error → retry once at the same tier with the error in the brief;
- verifiable failure (tests red, build broken after a real attempt) → one tier up. Before calling a fix done, run the existing tests of the modules it touched, not only new ones: a fix that breaks them has failed;
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
