| Task | PR size (files · lines) | Haiku alone | sonnet | ladder | opus-high | router |
|---|---|---|---|---|---|---|
| compress-206 | 1 · 1 | 2/2 | ✅ 1/1 · $0.21 · sonnet | – | – | – |
| jsx-array | 3 · 71 | 0/2 | ❌ 0/2 · $0.21 (0.19–0.24) · sonnet | ✅ 2/2 · $0.16 (0.12–0.19) · haiku+sonnet | ✅ 2/2 · $2.56 (2.36–2.75) · opus | ✅ 2/2 · $1.72 (1.65–1.78) · haiku+opus |
| method-not-allowed | 1 · 141 | 1/2 | ✅ 1/1 · $0.36 · sonnet | ✅ 1/1 · $2.06 · haiku+opus+sonnet | ✅ 1/1 · $1.58 · opus | ✅ 1/1 · $0.75 · haiku+sonnet |
| regexp-wildcard-middleware | 2 · 164 | 0/2 | ✅ 1/1 · $0.27 · sonnet | ✅ 1/1 · $0.47 · haiku+opus+sonnet | ✅ 1/1 · $0.84 · opus | ✅ 1/1 · $0.42 · haiku+sonnet |
| trie-suffix-wildcard | 2 · 143 | 1/2 | ✅ 2/2 · $0.23 (0.19–0.26) · sonnet | ✅ 2/2 · $0.87 (0.58–1.16) · haiku+opus+sonnet | ✅ 2/2 · $0.97 (0.82–1.12) · opus | ✅ 2/2 · $0.19 (0.12–0.26) · haiku+sonnet |
| accepts-case | 1 · 16 | 2/2 | – | – | – | – |
| accepts-wildcard | 1 · 41 | 2/2 | – | – | – | – |
| batch-aug | 3 · 46 | 2/2 | – | – | – | – |
| batch-jul | 5 · 45 | 2/2 | – | – | – | – |
| cache-query | 1 · 166 | 2/2 | – | – | – | – |
| content-type-case | 3 · 26 | 2/2 | – | – | – | – |
| csrf-options | 1 · 2 | 2/2 | – | – | – | – |
| etag-ows | 1 · 3 | 2/2 | – | – | – | – |
| etag-stream-digest | 1 · 54 | 2/2 | – | – | – | – |
| jwt-bad-signature | 1 · 13 | 2/2 | – | – | – | – |
| mount-middleware | 2 · 111 | 2/2 | – | – | – | – |
| regexp-router-unsupported | 3 · 378 | 2/2 | – | – | – | – |
| secure-headers-csp | 1 · 18 | 2/2 | – | – | – | – |

Cells: solved runs / runs · mean cost per run (min–max over reps) · models used. PR size: source files and lines the merged fix changed, tests excluded. Haiku alone: solve rate of the `haiku` floor config (Haiku, low effort, no checks).

Totals over the 4 tasks every config ran (left out: compress-206).
Per-rep totals use complete reps only (1); cells above include every run.

| Config | Solved per rep | Cost per rep | Cost per solved task | Escalations | Total time |
|---|---|---|---|---|---|
| sonnet | 3/4 | $1.07 | $0.36 | – | 6 min |
| ladder | 4/4 | $3.31 | $0.83 | 3 | 21 min |
| opus-high | 4/4 | $5.59 | $1.40 | – | 19 min |
| router | 4/4 | $3.09 | $0.77 | 0 | 16 min |

Routed runs: route.py at cc8e5fe.

By difficulty (from the `haiku` floor runs):

| Config | hard: floor fails half or more (4 tasks) |
|---|---|
| sonnet | 4/6 solved · $0.25 per run |
| ladder | 6/6 solved · $0.77 per run |
| opus-high | 6/6 solved · $1.58 per run |
| router | 6/6 solved · $0.83 per run |
