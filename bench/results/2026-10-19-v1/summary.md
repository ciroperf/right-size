| Task | Expected tier | default | ladder | opus-high | router | sonnet |
|---|---|---|---|---|---|---|
| batch-aug | standard | ✅ 1/1 · $0.37 · 77s · opus | ✅ 1/1 · $0.01 · 31s · haiku | ✅ 1/1 · $0.40 · 69s · opus | ✅ 1/1 · $0.34 · 72s · haiku+opus | ✅ 1/1 · $0.08 · 29s · sonnet |
| cache-query | deep | ❌ 0/1 · $0.75 · 188s · opus | ❌ 0/1 · $0.02 · 113s · haiku | ❌ 0/1 · $0.91 · 228s · opus | ❌ 0/1 · $0.73 · 170s · haiku+opus | ❌ 0/1 · $0.14 · 57s · sonnet |
| compress-206 | mechanical | ✅ 1/1 · $0.18 · 32s · opus | ✅ 1/1 · $0.01 · 34s · haiku | ✅ 1/1 · $0.16 · 31s · opus | ✅ 1/1 · $0.06 · 30s · haiku+sonnet | ✅ 1/1 · $0.06 · 47s · sonnet |
| content-type-case | standard | ✅ 1/1 · $0.28 · 47s · opus | ✅ 1/1 · $0.01 · 34s · haiku | ✅ 1/1 · $0.31 · 58s · opus | ✅ 1/1 · $0.32 · 60s · haiku+opus | ✅ 1/1 · $0.07 · 35s · sonnet |
| csrf-options | deep | ✅ 1/1 · $0.14 · 32s · opus | ✅ 1/1 · $0.01 · 26s · haiku | ✅ 1/1 · $0.18 · 32s · opus | ✅ 1/1 · $0.20 · 38s · haiku+opus | ✅ 1/1 · $0.04 · 16s · sonnet |
| jsx-array | standard | ❌ 0/1 · $0.62 · 128s · opus | ❌ 0/1 · $0.02 · 80s · haiku | ❌ 0/1 · $1.51 · 260s · opus | ❌ 0/1 · $1.06 · 234s · haiku+opus | ❌ 0/1 · $0.12 · 38s · sonnet |
| jwt-bad-signature | deep | ✅ 1/1 · $0.20 · 39s · opus | ✅ 1/1 · $0.01 · 24s · haiku | ✅ 1/1 · $0.23 · 37s · opus | ✅ 1/1 · $0.19 · 37s · haiku+opus | ✅ 1/1 · $0.06 · 23s · sonnet |
| method-not-allowed | standard | ❌ 0/1 · $0.58 · 118s · opus | ❌ 0/1 · $0.02 · 85s · haiku | ❌ 0/1 · $0.69 · 150s · opus | ❌ 0/1 · $0.15 · 60s · haiku+sonnet | ❌ 0/1 · $0.19 · 75s · sonnet |
| regexp-router-unsupported | deep | ❌ 0/1 · $3.49 · 975s · opus | ❌ 0/1 · $0.01 · 62s · haiku | ❌ 0/1 · $3.31 · 1019s · opus | ❌ 0/1 · $0.18 · 64s · haiku+sonnet | ❌ 0/1 · $0.28 · 126s · sonnet |
| trie-suffix-wildcard | deep | ✅ 1/1 · $0.53 · 118s · opus | ✅ 1/1 · $0.01 · 56s · haiku | ❌ 0/1 · $0.76 · 162s · opus | ✅ 1/1 · $1.00 · 196s · haiku+opus+sonnet | ✅ 1/1 · $0.14 · 51s · sonnet |

Cells: solved runs / runs · mean cost per run · mean wall time · models used.

| Config | Solved | Total cost | Cost per solved task | Mean cost per run | Escalations | Total tokens | Total time |
|---|---|---|---|---|---|---|---|
| default | 6/10 | $7.15 | $1.19 | $0.71 | – | 9.63M | 29 min |
| ladder | 6/10 | $0.12 | $0.02 | $0.01 | 0 | 4.88M | 9 min |
| opus-high | 5/10 | $8.46 | $1.69 | $0.85 | – | 11.06M | 34 min |
| router | 6/10 | $4.23 | $0.70 | $0.42 | 1 | 6.60M | 16 min |
| sonnet | 6/10 | $1.18 | $0.20 | $0.12 | – | 2.74M | 8 min |
