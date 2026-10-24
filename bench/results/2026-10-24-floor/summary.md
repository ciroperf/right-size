| Task | PR size (files · lines) | Haiku alone | haiku |
|---|---|---|---|
| accepts-case | 1 · 16 | 2/2 | ✅ 2/2 · $0.01 (0.01–0.01) · haiku |
| accepts-wildcard | 1 · 41 | 2/2 | ✅ 2/2 · $0.01 (0.01–0.01) · haiku |
| batch-aug | 3 · 46 | 2/2 | ✅ 2/2 · $0.01 (0.01–0.01) · haiku |
| batch-jul | 5 · 45 | 2/2 | ✅ 2/2 · $0.02 (0.02–0.03) · haiku |
| cache-query | 1 · 166 | 2/2 | ✅ 2/2 · $0.03 (0.02–0.03) · haiku |
| compress-206 | 1 · 1 | 2/2 | ✅ 2/2 · $0.01 (0.01–0.01) · haiku |
| content-type-case | 3 · 26 | 2/2 | ✅ 2/2 · $0.01 (0.01–0.01) · haiku |
| csrf-options | 1 · 2 | 2/2 | ✅ 2/2 · $0.01 (0.01–0.01) · haiku |
| etag-ows | 1 · 3 | 2/2 | ✅ 2/2 · $0.01 (0.01–0.01) · haiku |
| etag-stream-digest | 1 · 54 | 2/2 | ✅ 2/2 · $0.01 (0.01–0.01) · haiku |
| jsx-array | 3 · 71 | 0/2 | ❌ 0/2 · $0.03 (0.02–0.03) · haiku |
| jwt-bad-signature | 1 · 13 | 2/2 | ✅ 2/2 · $0.01 (0.01–0.01) · haiku |
| method-not-allowed | 1 · 141 | 1/2 | ⚠️ 1/2 · $0.03 (0.03–0.03) · haiku |
| mount-middleware | 2 · 111 | 2/2 | ✅ 2/2 · $0.02 (0.02–0.02) · haiku |
| regexp-router-unsupported | 3 · 378 | 2/2 | ✅ 2/2 · $0.07 (0.03–0.10) · haiku |
| regexp-wildcard-middleware | 2 · 164 | 0/2 | ❌ 0/2 · $0.10 (0.09–0.10) · haiku |
| secure-headers-csp | 1 · 18 | 2/2 | ✅ 2/2 · $0.01 (0.01–0.01) · haiku |
| trie-suffix-wildcard | 2 · 143 | 1/2 | ⚠️ 1/2 · $0.01 (0.01–0.02) · haiku |

Cells: solved runs / runs · mean cost per run (min–max over reps) · models used. PR size: source files and lines the merged fix changed, tests excluded. Haiku alone: solve rate of the `haiku` floor config (Haiku, low effort, no checks).

Totals over the 18 tasks every config ran.

| Config | Solved per rep | Cost per rep | Cost per solved task | Escalations | Total time |
|---|---|---|---|---|---|
| haiku | 15.0 ± 0.0 of 18 (15–15) | $0.39 ± 0.05 ($0.36–$0.43) | $0.03 | – | 46 min |

By difficulty (from the `haiku` floor runs):

| Config | easy: floor solves (14 tasks) | hard: floor fails half or more (4 tasks) |
|---|---|---|
| haiku | 28/28 solved · $0.02 per run | 2/8 solved · $0.04 per run |
