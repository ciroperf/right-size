# v1 rerun, 2026-10-21: trie with the fixed prompt, ladder with fresh-brief escalation

Two things rerun after `../2026-10-21-v1-checks/`, one run each:

- **trie-suffix-wildcard** for all three configs, with the prompt fixed on the
  v1-results branch (regex characters in the prefix are literal, registration order).
- **ladder** on regexp-router-unsupported, jsx-array and cache-query, with route.py
  at commit 1154404: a model change starts a fresh session with a brief instead of
  resuming, and reviews may run probes.

| Task | Config | Before | Now | Path |
|---|---|---|---|---|
| trie-suffix-wildcard | sonnet | ❌ $0.21 (old prompt) | ✅ $0.23 | Sonnet |
| trie-suffix-wildcard | ladder | ✅ $0.26 (old prompt) | ✅ $0.38 | Haiku (empty diff) → Sonnet |
| trie-suffix-wildcard | router | ❌ $0.38 (old prompt) | ✅ $0.10 | classifier picked mechanical, Haiku |
| regexp-router-unsupported | ladder | ✅ $1.93 | ✅ $0.16 | Haiku (tests red) → Sonnet, fresh brief |
| jsx-array | ladder | ✅ $0.35 | ✅ $0.14 | Haiku, tests and Sonnet review passed |
| cache-query | ladder | ❌ $0.08 | ✅ $0.10 | Haiku, tests and Sonnet review passed |

## Findings

1. **The fresh brief removes most of an escalation's cost.** regexp went from $1.93
   (Opus resuming the whole Haiku conversation uncached) to $0.16: Sonnet got the
   task, the diff and the failing test output in a new session.
2. **The probes never ran.** Both reviews say they couldn't run anything: headless
   sessions deny shell commands that aren't allowed explicitly. cache-query passing
   this time is Haiku getting it right (it cloned the request), not the review
   catching a defect. Fixed afterwards (a23f756): the reviewer gets the project's
   test runner, and denied commands are recorded. The effect is not measured yet.
3. One run per cell: Haiku solving jsx and cache-query on the first try here, after
   failing them in the first pass, is as likely variance as improvement.

With these rows replacing the invalid ones, v1 rep 1 stands at
sonnet 10/11 $2.13, ladder 11/11 $1.70, router 11/11 $10.03 (the router's other
rows are from `../2026-10-21-v1-checks/`, before the fresh brief).
