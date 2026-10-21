| Task | Expected tier | ladder | sonnet |
|---|---|---|---|
| batch-jul | standard | ✅ 1/1 · $0.01 · 48s · haiku | ✅ 1/1 · $0.15 · 34s · sonnet |
| cache-query | deep | ❌ 0/1 · $0.04 · 172s · haiku | ❌ 0/1 · $0.16 · 54s · sonnet |
| jsx-array | standard | ❌ 0/1 · $0.01 · 57s · haiku | ❌ 0/1 · $0.45 · 224s · sonnet |
| method-not-allowed | standard | ✅ 1/1 · $0.03 · 139s · haiku | ✅ 1/1 · $0.20 · 89s · sonnet |
| regexp-router-unsupported | deep | ✅ 1/1 · $0.04 · 182s · haiku | ✅ 1/1 · $0.38 · 170s · sonnet |
| trie-suffix-wildcard | deep | ✅ 1/1 · $0.02 · 79s · haiku | ✅ 1/1 · $0.18 · 87s · sonnet |

Cells: solved runs / runs · mean cost per run · mean wall time · models used.

| Config | Solved | Total cost | Cost per solved task | Mean cost per run | Escalations | Total tokens | Total time |
|---|---|---|---|---|---|---|---|
| ladder | 4/6 | $0.15 | $0.04 | $0.02 | 0 | 4.39M | 11 min |
| sonnet | 4/6 | $1.53 | $0.38 | $0.26 | – | 3.95M | 11 min |
