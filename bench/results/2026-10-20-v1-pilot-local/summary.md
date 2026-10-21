| Task | Expected tier | ladder | router | sonnet |
|---|---|---|---|---|
| batch-aug | standard | ✅ 1/1 · $0.01 · 35s · haiku | ✅ 1/1 · $0.37 · 80s · haiku+opus | ✅ 1/1 · $0.12 · 38s · sonnet |
| batch-jul | standard | ✅ 1/1 · $0.02 · 64s · haiku | ✅ 1/1 · $0.77 · 149s · haiku+opus | ✅ 1/1 · $0.18 · 54s · sonnet |
| cache-query | deep | ❌ 0/1 · $0.02 · 89s · haiku | ❌ 0/1 · $0.83 · 164s · haiku+opus | ❌ 0/1 · $0.40 · 224s · sonnet |
| compress-206 | mechanical | ✅ 1/1 · $0.01 · 25s · haiku | ✅ 1/1 · $0.19 · 24s · haiku+sonnet | ✅ 1/1 · $0.08 · 20s · sonnet |
| content-type-case | standard | ✅ 1/1 · $0.01 · 38s · haiku | ✅ 1/1 · $0.43 · 65s · haiku+opus | ✅ 1/1 · $0.09 · 20s · sonnet |
| csrf-options | deep | ✅ 1/1 · $0.01 · 35s · haiku | ✅ 1/1 · $0.47 · 43s · haiku+opus | ✅ 1/1 · $0.08 · 20s · sonnet |
| jsx-array | standard | ❌ 0/1 · $0.03 · 95s · haiku | ❌ 0/1 · $1.27 · 197s · haiku+opus | ❌ 0/1 · $0.21 · 67s · sonnet |
| jwt-bad-signature | deep | ✅ 1/1 · $0.01 · 42s · haiku | ✅ 1/1 · $0.31 · 54s · haiku+opus | ✅ 1/1 · $0.12 · 50s · sonnet |
| method-not-allowed | standard | ❌ 0/1 · $0.02 · 70s · haiku | ❌ 0/1 · $0.49 · 148s · haiku+sonnet | ❌ 0/1 · $0.35 · 117s · sonnet |
| regexp-router-unsupported | deep | ❌ 0/1 · $0.02 · 94s · haiku | ❌ 0/1 · $0.47 · 165s · haiku+sonnet | ❌ 0/1 · $0.47 · 117s · sonnet |
| trie-suffix-wildcard | deep | ❌ 0/1 · $0.01 · 30s · haiku | ✅ 1/1 · $0.43 · 134s · haiku+sonnet | ❌ 0/1 · $0.21 · 61s · sonnet |

Cells: solved runs / runs · mean cost per run · mean wall time · models used.

| Config | Solved | Total cost | Cost per solved task | Mean cost per run | Escalations | Total tokens | Total time |
|---|---|---|---|---|---|---|---|
| ladder | 6/11 | $0.17 | $0.03 | $0.02 | 0 | 6.20M | 10 min |
| router | 7/11 | $6.03 | $0.86 | $0.55 | 0 | 8.94M | 20 min |
| sonnet | 6/11 | $2.30 | $0.38 | $0.21 | – | 5.18M | 13 min |
