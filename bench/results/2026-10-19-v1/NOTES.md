# v1, 2026-10-19: partial run (rep 1 only)

Stopped on purpose after 50 of 165 planned runs: every config ran each of the
11 v1 tasks once, except `batch-jul` (not run). Results are kept because they
drove the changes listed below; they are not a full v1 result.

What these runs used:

- Runner with the harness fixes of 086f481 (vitest start check, broader Bash
  allowlist, explicit headless escalation note in `route.py`).
- The **old** v1 prompts and the **old** risk floor (deep). Both changed after
  this run (5e8e9fc, 8b34c8c, 136b50b), so a rerun is not comparable cell by cell.

## Findings

1. **Two groups of tasks, no middle.** Five tasks were solved by every config,
   four by none (`regexp-router-unsupported`, `jsx-array`, `method-not-allowed`,
   `cache-query`). Only `trie-suffix-wildcard` split the configs, and it flipped
   between the pilot and this run (opus-high and sonnet swapped results), so
   one rep says little about it.
2. **The four unsolved tasks were mostly spec gaps.** Every failing run tripped
   the same one or two PR tests, checking behavior the prompt never stated. With
   the PR tests visible, Haiku at low solved `regexp-router-unsupported` ($0.03)
   and `trie-suffix-wildcard` ($0.01); blind, opus-high spent $3.31 on the first
   and failed. Prompts were revised; see `../2026-10-19-v1-checks/`.
3. **Ladder (Haiku low, escalate on failure) matched every other config** on
   solved tasks at about 1/60 of default's cost ($0.12 vs $7.15).
4. **The deep risk floor bought nothing.** The router sent 6 of 10 tasks to Opus
   for the risk floor; on the security bug fixes Sonnet and Haiku solved the same
   tasks. The floor is now `standard` (deep for design changes or no tests).
5. **Escalation only fires on failures the agent can see.** It worked when a check
   stayed red (router on `trie-suffix-wildcard`, standard → deep; a contradictory
   test sent Haiku straight to deep). It never fired when the agent wrote its own
   test, saw it pass, and missed the hidden spec: the common failure in v1.
6. **More effort did not help:** opus-high cost the most and solved one task fewer
   than default.

## Next steps (not done: out of credit)

- Rerun v1 with the revised prompts and risk floor (10 tasks, 150 runs, ~$45-60).
  Cheaper and almost as informative: 3 reps of sonnet, router and ladder, 1 rep of
  default and opus-high as references.
- Add tasks that Haiku fails even with a clear spec. Without them the benchmark
  cannot show what the higher tiers or escalation are worth.
- `diff_lines` counts tracked files only, so a task that creates a new file
  (method-not-allowed) can read 0 lines although the agent wrote code.
