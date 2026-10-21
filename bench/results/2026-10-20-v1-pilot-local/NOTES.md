# v1 pilot, local run, 2026-10-20: rep 1 of sonnet, ladder, router

A second pilot of the v1 set, run locally with the same old prompts and the old
deep risk floor as `../2026-10-19-v1/`, before external checks existed. Kept
because it drove two changes; it is not a v1 result.

- Totals: ladder 6/11 $0.17, sonnet 6/11 $2.30, router 7/11 $6.03. No run
  escalated: every session that failed stopped with a wrong answer and never
  asked to escalate, at every tier. That led to external checks in route.py.
- Most of the router's cost was the deep risk floor: Opus on small security
  fixes that Haiku and Sonnet solved. That led to the risk floor becoming
  "review at deep" instead of "start at deep".
- regexp-router-unsupported, jsx-array, method-not-allowed and cache-query
  results are invalid: their prompts left out behavior the PR tests check.
