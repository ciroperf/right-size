| Task | Expected tier | default | delegate | right-size | router-split | router-standard | router |
|---|---|---|---|---|---|---|---|
| batch-aug | standard | ✅ 1/1 · $0.35 · 56s · opus | ✅ 1/1 · $0.96 · 97s · haiku+opus+sonnet | ✅ 1/1 · $0.64 · 76s · opus | ✅ 1/1 · $0.69 · 122s · haiku+opus+sonnet | ✅ 1/1 · $0.24 · 39s · sonnet | ✅ 1/1 · $0.60 · 94s · haiku+opus |
| batch-jul | standard | ✅ 1/1 · $0.67 · 116s · opus | ✅ 1/1 · $1.13 · 156s · opus+sonnet | ✅ 1/1 · $0.69 · 120s · opus | ✅ 1/1 · $0.60 · 119s · haiku+opus+sonnet | ✅ 1/1 · $0.17 · 45s · sonnet | ✅ 1/1 · $0.88 · 163s · haiku+opus |

Cells: solved runs / runs · mean cost per run · mean wall time · models used.

| Config | Solved | Total cost | Cost per solved task | Mean cost per run | Escalations | Total tokens | Total time |
|---|---|---|---|---|---|---|---|
| default | 2/2 | $1.03 | $0.51 | $0.51 | – | 1.34M | 3 min |
| delegate | 2/2 | $2.09 | $1.05 | $1.05 | – | 3.10M | 4 min |
| right-size | 2/2 | $1.32 | $0.66 | $0.66 | – | 1.55M | 3 min |
| router-split | 2/2 | $1.29 | $0.64 | $0.64 | 0 | 1.94M | 4 min |
| router-standard | 2/2 | $0.41 | $0.21 | $0.21 | 0 | 0.62M | 1 min |
| router | 2/2 | $1.48 | $0.74 | $0.74 | 0 | 2.08M | 4 min |
