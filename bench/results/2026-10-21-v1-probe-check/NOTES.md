# Probe check, 2026-10-21: does the reviewer run probes now? (route.py 46e3bff)

One ladder run on cache-query. Inconclusive: Haiku's attempt failed the existing
tests, Sonnet's passed them, and work on `standard` outside a risk area isn't
reviewed, so no review ran. Solved, $0.19. The check needs a task where the
mechanical attempt passes the tests and reaches the review.
