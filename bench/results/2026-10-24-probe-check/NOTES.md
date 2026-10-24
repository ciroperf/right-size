# Probe check, 2026-10-24: reviews can now run probes (route.py 463b092)

Ladder on compress-206 and jsx-array; both solved on Haiku, both reviewed by Sonnet.
(A first jsx run was discarded: a task validation checked out another commit in
the shared Hono checkout while it ran.)

- **compress-206** ($0.08): the reviewer read the one-line diff and passed it
  without a probe; nothing was denied.
- **jsx-array** ($0.12): the reviewer wrote two throwaway test files, ran them and
  the existing jsx suites (1,942 passed), and passed the change. The record shows
  `probed: true`. One command was denied: writing the probe with a shell heredoc
  (`cat > file <<EOF`), which the allowlist doesn't cover; it then used the Write
  tool. The reviewer prompt now names the Write tool.

On 2026-10-21 the same reviews reported "Bash was denied" and ran nothing.
