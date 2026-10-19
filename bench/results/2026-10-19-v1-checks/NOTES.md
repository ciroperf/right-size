# v1 prompt checks, 2026-10-19

One run each of `sonnet` and `ladder` on the tasks whose prompts were revised
after the partial v1 run (`../2026-10-19-v1/`), to see whether the revisions close
the spec gaps before paying for a full rerun. Prompts as of 136b50b
(`method-not-allowed` and `cache-query` are from the second revision round).

| Task | sonnet | ladder | Note |
|---|---|---|---|
| trie-suffix-wildcard | ✅ | ✅ | |
| regexp-router-unsupported | ✅ | ✅ | unsolved by every config before |
| method-not-allowed | ✅ | ✅ | unsolved by every config before |
| batch-jul | ✅ | ✅ | not run in the partial v1 |
| jsx-array | ❌ | ❌ | real regression: the fixes break existing streaming tests; prompt left as is |
| cache-query | ❌ | ❌ | PR tests pin the internal cache key format and reword an unrelated message; removed from `sets.v1` |

Escalation probes run outside the runner (not stored here): a test that can't
pass (it asks for two different results from the same input) sent Haiku to deep
via `RIGHT-SIZE-ESCALATE: reasoning`. With the PR test visible, Haiku solved
`regexp-router-unsupported` and `trie-suffix-wildcard` on its own.
