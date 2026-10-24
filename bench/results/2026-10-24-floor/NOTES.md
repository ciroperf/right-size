# Difficulty floor, 2026-10-24: Haiku alone on every task, two runs each

Config `haiku`: Claude Haiku 5.5 at low effort for the whole session, no right-size,
no checks, no escalation. Its solve rate is each task's measured difficulty, taken
from outside the configurations being compared.

- 15 of 18 tasks solved in each run, $0.36–0.43 per run of all 18.
- Solved 2/2: 14 tasks, including several labelled `deep` by hand
  (regexp-router-unsupported) and the new mount-middleware.
- Failed at least once: jsx-array 0/2, regexp-wildcard-middleware 0/2,
  method-not-allowed 1/2, trie-suffix-wildcard 1/2. These form the `hard` set.

Reading: most of the benchmark is within reach of the cheapest model. A saving on
those tasks shows that a config doesn't overspend, not that its escalation works;
the `hard` set is where that is tested. trie passed in the first run and failed in
the second: with one run it would have been labelled easy.
