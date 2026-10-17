| Task | Expected tier | default | max | right-size |
|---|---|---|---|---|
| accepts-case | standard | ✅ $0.23 · 327k tok · 51s · opus | ✅ $0.73 · 898k tok · 147s · opus | ✅ $0.26 · 385k tok · 38s · opus |
| accepts-wildcard | standard | ✅ $0.29 · 435k tok · 43s · opus | ✅ $1.41 · 1237k tok · 367s · opus | ✅ $0.29 · 394k tok · 45s · opus |
| compress-206 | mechanical | ✅ $0.26 · 301k tok · 34s · opus | ✅ $0.38 · 549k tok · 87s · opus | ✅ $0.23 · 360k tok · 46s · opus |
| content-type-case | standard | ✅ $0.32 · 471k tok · 50s · opus | ✅ $1.34 · 1833k tok · 357s · opus | ✅ $0.44 · 724k tok · 94s · opus |
| csrf-options | deep | ✅ $0.22 · 323k tok · 36s · opus | ✅ $0.57 · 655k tok · 131s · opus | ✅ $0.28 · 398k tok · 38s · opus |
| etag-ows | mechanical | ✅ $0.21 · 251k tok · 42s · opus | ✅ $0.90 · 897k tok · 242s · opus | ✅ $0.27 · 394k tok · 52s · opus |
| etag-stream-digest | standard | ✅ $0.26 · 379k tok · 44s · opus | ✅ $1.23 · 823k tok · 343s · opus | ✅ $0.29 · 389k tok · 63s · opus |
| jwt-bad-signature | deep | ✅ $0.23 · 333k tok · 53s · opus | ✅ $1.11 · 1415k tok · 229s · opus | ✅ $0.27 · 348k tok · 51s · opus |
| secure-headers-csp | deep | ✅ $0.32 · 375k tok · 54s · opus | ✅ $1.24 · 1546k tok · 255s · opus | ✅ $0.42 · 557k tok · 56s · opus |
| trie-suffix-wildcard | deep | ✅ $0.97 · 1205k tok · 160s · opus | ✅ $4.10 · 5952k tok · 839s · opus | ❌ $1.01 · 1374k tok · 156s · opus |

| Config | Solved | Total cost | Cost per solved task | Total tokens | Total time |
|---|---|---|---|---|---|
| default | 10/10 | $3.31 | $0.33 | 4.40M | 9 min |
| max | 10/10 | $13.01 | $1.30 | 15.80M | 50 min |
| right-size | 9/10 | $3.77 | $0.42 | 5.32M | 11 min |
