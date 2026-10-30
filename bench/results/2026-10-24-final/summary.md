| Task | PR size (files · lines) | Haiku alone | sonnet | ladder | opus-high | router |
|---|---|---|---|---|---|---|
| compress-206 | 1 · 1 | 2/2 | ✅ 1/1 · $0.21 · sonnet | – | – | – |
| jsx-array | 3 · 71 | 0/2 | ❌ 0/2 · $0.21 (0.19–0.24) · sonnet | ✅ 2/2 · $0.16 (0.12–0.19) · haiku+sonnet | ✅ 2/2 · $2.56 (2.36–2.75) · opus | ✅ 2/2 · $1.72 (1.65–1.78) · haiku+opus |
| method-not-allowed | 1 · 141 | 1/2 | ✅ 2/2 · $0.49 (0.36–0.62) · sonnet | ✅ 2/2 · $1.12 (0.18–2.06) · haiku+opus+sonnet | ✅ 2/2 · $1.46 (1.34–1.58) · opus | ✅ 2/2 · $1.22 (0.75–1.69) · haiku+opus+sonnet |
| regexp-wildcard-middleware | 2 · 164 | 0/2 | ✅ 2/2 · $0.38 (0.27–0.50) · sonnet | ✅ 2/2 · $1.02 (0.47–1.57) · haiku+opus+sonnet | ✅ 2/2 · $1.02 (0.84–1.20) · opus | ✅ 2/2 · $0.77 (0.42–1.11) · haiku+opus+sonnet |
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

| Config | Solved per rep | Cost per rep | Cost per solved task | Escalations | Total time |
|---|---|---|---|---|---|
| sonnet | 3.0 ± 0.0 of 4 (3–3) | $1.31 ± 0.33 ($1.07–$1.54) | $0.44 | – | 14 min |
| ladder | 4.0 ± 0.0 of 4 (4–4) | $3.17 ± 0.20 ($3.03–$3.31) | $0.79 | 5 | 42 min |
| opus-high | 4.0 ± 0.0 of 4 (4–4) | $6.00 ± 0.58 ($5.59–$6.41) | $1.50 | – | 38 min |
| router | 4.0 ± 0.0 of 4 (4–4) | $3.89 ± 1.14 ($3.09–$4.70) | $0.97 | 2 | 39 min |

Routed runs: route.py at cc8e5fe.

By difficulty (from the `haiku` floor runs):

| Config | hard: floor fails half or more (4 tasks) |
|---|---|
| sonnet | 6/8 solved · $0.33 per run |
| ladder | 8/8 solved · $0.79 per run |
| opus-high | 8/8 solved · $1.50 per run |
| router | 8/8 solved · $0.97 per run |
