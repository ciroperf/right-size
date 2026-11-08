| Task | PR size (files · lines) | Haiku alone | ladder | sonnet | opus-high | router |
|---|---|---|---|---|---|---|
| accepts-case | 1 · 16 | 2/2 | ✅ 2/2 · $0.05 (0.05–0.06) · haiku+sonnet | ✅ 2/2 · $0.07 (0.06–0.08) · sonnet | – | – |
| accepts-wildcard | 1 · 41 | 2/2 | ✅ 2/2 · $0.04 (0.04–0.04) · haiku+sonnet | ✅ 2/2 · $0.09 (0.06–0.11) · sonnet | – | – |
| batch-aug | 3 · 46 | 2/2 | ✅ 2/2 · $0.05 (0.05–0.05) · haiku+sonnet | ✅ 2/2 · $0.11 (0.10–0.12) · sonnet | – | – |
| batch-jul | 5 · 45 | 2/2 | ✅ 2/2 · $0.06 (0.06–0.07) · haiku+sonnet | ✅ 2/2 · $0.17 (0.14–0.19) · sonnet | – | – |
| cache-query | 1 · 166 | 2/2 | ✅ 2/2 · $0.24 (0.08–0.40) · haiku+opus+sonnet | ✅ 2/2 · $0.27 (0.18–0.36) · sonnet | – | – |
| compress-206 | 1 · 1 | 2/2 | ✅ 2/2 · $0.06 (0.05–0.08) · haiku+sonnet | ✅ 2/2 · $0.16 (0.10–0.21) · sonnet | – | – |
| content-type-case | 3 · 26 | 2/2 | ✅ 2/2 · $0.06 (0.05–0.07) · haiku+sonnet | ✅ 2/2 · $0.11 (0.10–0.12) · sonnet | – | – |
| csrf-options | 1 · 2 | 2/2 | ✅ 2/2 · $0.04 (0.04–0.04) · haiku+sonnet | ✅ 2/2 · $0.14 (0.09–0.19) · sonnet | – | – |
| etag-ows | 1 · 3 | 2/2 | ✅ 2/2 · $0.04 (0.04–0.04) · haiku+sonnet | ✅ 2/2 · $0.06 (0.05–0.07) · sonnet | – | – |
| etag-stream-digest | 1 · 54 | 2/2 | ✅ 2/2 · $0.04 (0.04–0.04) · haiku+sonnet | ✅ 2/2 · $0.10 (0.08–0.11) · sonnet | – | – |
| jsx-array | 3 · 71 | 0/2 | ✅ 2/2 · $0.16 (0.12–0.19) · haiku+sonnet | ❌ 0/2 · $0.21 (0.19–0.24) · sonnet | ✅ 2/2 · $2.56 (2.36–2.75) · opus | ✅ 2/2 · $1.72 (1.65–1.78) · haiku+opus |
| jwt-bad-signature | 1 · 13 | 2/2 | ✅ 2/2 · $0.05 (0.04–0.06) · haiku+sonnet | ✅ 2/2 · $0.09 (0.07–0.12) · sonnet | – | – |
| method-not-allowed | 1 · 141 | 1/2 | ✅ 2/2 · $1.12 (0.18–2.06) · haiku+opus+sonnet | ✅ 2/2 · $0.49 (0.36–0.62) · sonnet | ✅ 2/2 · $1.46 (1.34–1.58) · opus | ✅ 2/2 · $1.22 (0.75–1.69) · haiku+opus+sonnet |
| mount-middleware | 2 · 111 | 2/2 | ✅ 2/2 · $0.79 (0.77–0.80) · haiku+opus+sonnet | ✅ 2/2 · $0.20 (0.20–0.20) · sonnet | – | – |
| regexp-router-unsupported | 3 · 378 | 2/2 | ⚠️ 1/2 · $1.98 (1.60–2.36) · haiku+opus+sonnet | ❌ 0/2 · $0.22 (0.21–0.22) · sonnet | – | – |
| regexp-wildcard-middleware | 2 · 164 | 0/2 | ✅ 2/2 · $1.02 (0.47–1.57) · haiku+opus+sonnet | ✅ 2/2 · $0.38 (0.27–0.50) · sonnet | ✅ 2/2 · $1.02 (0.84–1.20) · opus | ✅ 2/2 · $0.77 (0.42–1.11) · haiku+opus+sonnet |
| secure-headers-csp | 1 · 18 | 2/2 | ✅ 2/2 · $0.06 (0.06–0.06) · haiku+sonnet | ✅ 2/2 · $0.14 (0.13–0.15) · sonnet | – | – |
| trie-suffix-wildcard | 2 · 143 | 1/2 | ✅ 2/2 · $0.87 (0.58–1.16) · haiku+opus+sonnet | ✅ 2/2 · $0.23 (0.19–0.26) · sonnet | ✅ 2/2 · $0.97 (0.82–1.12) · opus | ✅ 2/2 · $0.19 (0.12–0.26) · haiku+sonnet |

Cells: solved runs / runs · mean cost per run (min–max over reps) · models used. PR size: source files and lines the merged fix changed, tests excluded. Haiku alone: solve rate of the `haiku` floor config (Haiku, low effort, no checks).

Totals over the 4 tasks every config ran (left out: accepts-case, accepts-wildcard, batch-aug, batch-jul, cache-query, compress-206, content-type-case, csrf-options, etag-ows, etag-stream-digest, jwt-bad-signature, mount-middleware, regexp-router-unsupported, secure-headers-csp).

| Config | Solved per rep | Cost per rep | Cost per solved task | Escalations | Total time |
|---|---|---|---|---|---|
| ladder | 4.0 ± 0.0 of 4 (4–4) | $3.17 ± 0.20 ($3.03–$3.31) | $0.79 | 5 | 42 min |
| sonnet | 3.0 ± 0.0 of 4 (3–3) | $1.31 ± 0.33 ($1.07–$1.54) | $0.44 | – | 14 min |
| opus-high | 4.0 ± 0.0 of 4 (4–4) | $6.00 ± 0.58 ($5.59–$6.41) | $1.50 | – | 38 min |
| router | 4.0 ± 0.0 of 4 (4–4) | $3.89 ± 1.14 ($3.09–$4.70) | $0.97 | 2 | 39 min |

Routed runs: route.py at cc8e5fe.

By difficulty (from the `haiku` floor runs):

| Config | hard: floor fails half or more (4 tasks) |
|---|---|
| ladder | 8/8 solved · $0.79 per run |
| sonnet | 6/8 solved · $0.33 per run |
| opus-high | 8/8 solved · $1.50 per run |
| router | 8/8 solved · $0.97 per run |
