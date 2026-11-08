# Final run, 2026-10-24 to 2026-11-08

Hono, 18 tasks merged after the training cutoff, 2 reps each. Claude Code 2.1.302 throughout.
Every ladder and router record ran route.py at cc8e5fe; runs from earlier router versions are in
`superseded-*/` and don't count.

Summaries: `summary.md` (all configs, totals on the 4 tasks every config ran) and
`summary-sonnet-ladder.md` (sonnet vs ladder on all 18). Task difficulty comes from
`../2026-10-24-floor` (Haiku at low effort, no checks): it solves 14 tasks in both reps and
fails 4 at least once (the hard set).

## Results

Hard set (4 tasks Haiku alone fails at least half the time), per run:

| Config | Solved | Mean cost |
|---|---|---|
| sonnet | 6/8 | $0.33 |
| ladder | 8/8 | $0.79 |
| router (`--classify`) | 8/8 | $0.97 |
| opus-high | 8/8 | $1.50 |

All 18 tasks, per rep: ladder 17.5 ± 0.7 solved for $6.75 ± 0.99; sonnet 16.0 ± 0.0 for
$3.22 ± 0.10. Haiku alone (floor) solves 15 per rep for about $0.40.

## What the numbers say

- The ladder solved everything opus-high solved on the hard set at about half the cost, and
  more than Sonnet alone overall (35/36 vs 32/36), at about twice Sonnet's cost.
- On easy tasks the ladder usually ends on Haiku plus a Sonnet review for $0.04 to $0.08,
  cheaper than Sonnet alone. Its cost comes from the few tasks that escalate to Opus
  (mount-middleware $0.79, regexp-router-unsupported up to $2.36, method-not-allowed up to $2.06).
- Cost variance is large for the ladder on escalating tasks (method-not-allowed $0.18 vs
  $2.06 across reps); Sonnet's cost barely moves.
- The classifier (router) solved the same hard tasks as the ladder and cost more on average.

## Regressions and failures

- **regexp-router-unsupported, ladder rep 1 failed ($2.36).** Haiku alone solves this task.
  The ladder's Sonnet attempt passed the tests but rebuilt the matcher on every `add()`; the
  Opus review rejected it for quadratic registration cost (a real issue it measured). The Opus
  attempt then switched to per-method checker tries, which broke two PR tests (static paths
  containing a colon), and its deep review didn't catch it. Rep 2 solved it for $1.60.
- **regexp-router-unsupported, sonnet 0/2** and **jsx-array, sonnet 0/2.**
- **Risk areas in ladder mode:** without `--classify` the router doesn't know a task is in a
  risk area, so jwt-bad-signature got a Sonnet review instead of the deep one. Fixed after
  this run with `--risk`; these records predate it.
