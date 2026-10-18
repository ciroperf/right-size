| Task | Expected tier | default | delegate | right-size | router |
|---|---|---|---|---|---|
| batch-aug | standard | ✅ $0.35 · 364k tok · 56s · opus | ✅ $0.96 · 1566k tok · 97s · haiku+opus+sonnet | ✅ $0.64 · 572k tok · 76s · opus | ✅ $0.60 · 682k tok · 94s · haiku+opus |
| batch-jul | standard | ✅ $0.67 · 976k tok · 116s · opus | ✅ $1.13 · 1539k tok · 156s · opus+sonnet | ✅ $0.69 · 981k tok · 120s · opus | ✅ $0.88 · 1401k tok · 163s · haiku+opus |

| Config | Solved | Total cost | Cost per solved task | Total tokens | Total time |
|---|---|---|---|---|---|
| default | 2/2 | $1.03 | $0.51 | 1.34M | 3 min |
| delegate | 2/2 | $2.09 | $1.05 | 3.10M | 4 min |
| right-size | 2/2 | $1.32 | $0.66 | 1.55M | 3 min |
| router | 2/2 | $1.48 | $0.74 | 2.08M | 4 min |
