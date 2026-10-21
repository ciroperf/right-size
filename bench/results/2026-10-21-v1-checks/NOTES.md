# v1 with checks, 2026-10-21: rep 1 of sonnet, ladder, router

First run of `route.py` with external checks (commit 6db808f): after each headless
attempt the router fails it when no file changed, when the existing tests of the
changed files fail (`npx vitest --run --changed`), or when a review one tier up
(deep for risk areas) rejects the diff, and resumes the session one tier up.
The risk floor was already "size like any change, review at deep".

The sonnet results for compress, content-type, csrf, jwt, trie and the two batches
were copied from the pilot run (`../2026-10-20-v1-pilot-local/`): same prompts,
same setup, no router involved.

| Task | sonnet | ladder | router |
|---|---|---|---|
| compress-206 | ✅ $0.08 | ✅ $0.04 | ✅ $0.10 |
| csrf-options | ✅ $0.08 | ✅ $0.04 | ✅ $0.22 |
| jwt-bad-signature | ✅ $0.12 | ✅ $0.04 | ✅ $0.16 |
| content-type-case | ✅ $0.09 | ✅ $0.05 | ✅ $0.20 |
| trie-suffix-wildcard | ❌ $0.21 | ✅ $0.26 | ❌ $0.38 |
| jsx-array | ✅ $0.39 | ✅ $0.35 | ✅ $3.53 |
| regexp-router-unsupported | ❌ $0.22 | ✅ $1.93 | ✅ $2.52 |
| method-not-allowed | ✅ $0.39 | ✅ $0.45 | ✅ $1.38 |
| cache-query | ✅ $0.23 | ❌ $0.08 | ✅ $1.05 |
| batch-aug | ✅ $0.12 | ✅ $0.05 | ✅ $0.21 |
| batch-jul | ✅ $0.18 | ✅ $0.25 | ✅ $0.56 |
| **Total** | **9/11 · $2.10** | **10/11 · $3.54** | **10/11 · $10.31** |

One run per cell: a one-task difference between configs can be noise.

## Caveats

- **trie-suffix-wildcard** used a prompt that left out two behaviors the PR tests
  check (regex characters in the prefix, registration order); sonnet and router
  failed exactly those. The prompt was fixed afterwards on the v1-results branch,
  so the trie row needs a rerun before it counts.
- **method-not-allowed and cache-query** were rerun after a second prompt fix;
  the first attempts are in `superseded-prompts/` and don't count.

## Findings

1. **Checks make escalation fire.** In the pilot, no config ever escalated. Here
   the ladder climbed on jsx-array (Haiku failed the tests), regexp (Haiku to Sonnet
   to Opus) and trie (a review rejected Haiku's empty change).
2. **The classifier doesn't pay for itself.** Same solved count as the ladder at
   about 3x the cost: it picked deep (once at high effort) for jsx and regexp.
3. **Resuming on a bigger model is the expensive part of an escalation.** On
   regexp, $1.64 of the ladder's $1.93 was Opus re-reading the whole earlier
   conversation uncached. Since then a model change starts a fresh session with
   a brief.
4. **Tests and a read-only review can both miss a defect.** On cache-query,
   Haiku's change consumed the request body; the existing tests and a Sonnet
   review passed it. Since then the reviewer may write and run a throwaway probe.
