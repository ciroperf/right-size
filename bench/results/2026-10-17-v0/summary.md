| Task | Expected tier | default | max | right-size |
|---|---|---|---|---|
| accepts-case | standard | ✅ 1/1 · $0.23 · 51s · opus | ✅ 1/1 · $0.73 · 147s · opus | ✅ 1/1 · $0.26 · 38s · opus |
| accepts-wildcard | standard | ✅ 1/1 · $0.29 · 43s · opus | ✅ 1/1 · $1.41 · 367s · opus | ✅ 1/1 · $0.29 · 45s · opus |
| compress-206 | mechanical | ✅ 1/1 · $0.26 · 34s · opus | ✅ 1/1 · $0.38 · 87s · opus | ✅ 1/1 · $0.23 · 46s · opus |
| content-type-case | standard | ✅ 1/1 · $0.32 · 50s · opus | ✅ 1/1 · $1.34 · 357s · opus | ✅ 1/1 · $0.44 · 94s · opus |
| csrf-options | deep | ✅ 1/1 · $0.22 · 36s · opus | ✅ 1/1 · $0.57 · 131s · opus | ✅ 1/1 · $0.28 · 38s · opus |
| etag-ows | mechanical | ✅ 1/1 · $0.21 · 42s · opus | ✅ 1/1 · $0.90 · 242s · opus | ✅ 1/1 · $0.27 · 52s · opus |
| etag-stream-digest | standard | ✅ 1/1 · $0.26 · 44s · opus | ✅ 1/1 · $1.23 · 343s · opus | ✅ 1/1 · $0.29 · 63s · opus |
| jwt-bad-signature | deep | ✅ 1/1 · $0.23 · 53s · opus | ✅ 1/1 · $1.11 · 229s · opus | ✅ 1/1 · $0.27 · 51s · opus |
| secure-headers-csp | deep | ✅ 1/1 · $0.32 · 54s · opus | ✅ 1/1 · $1.24 · 255s · opus | ✅ 1/1 · $0.42 · 56s · opus |
| trie-suffix-wildcard | deep | ✅ 1/1 · $0.97 · 160s · opus | ✅ 1/1 · $4.10 · 839s · opus | ❌ 0/1 · $1.01 · 156s · opus |

Cells: solved runs / runs · mean cost per run · mean wall time · models used.

| Config | Solved | Total cost | Cost per solved task | Mean cost per run | Escalations | Total tokens | Total time |
|---|---|---|---|---|---|---|---|
| default | 10/10 | $3.31 | $0.33 | $0.33 | – | 4.40M | 9 min |
| max | 10/10 | $13.01 | $1.30 | $1.30 | – | 15.80M | 50 min |
| right-size | 9/10 | $3.77 | $0.42 | $0.38 | – | 5.32M | 11 min |
