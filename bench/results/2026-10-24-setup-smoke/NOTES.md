# Smoke test: generated subagents run on their tier's model, 2026-10-24

Claude Code 2.1.302 (Claude Code). A throwaway git repo with the four agents `right-size-setup`
generates (from `skills/right-size-setup/templates/claude-code/` and
`harnesses/claude-code.yaml`), and one headless session on Sonnet:

```bash
claude -p "Delegate this to the right-size-mechanical subagent and do nothing yourself: append the line 'world' to a.txt."   --model sonnet --output-format json --setting-sources project --strict-mcp-config   --permission-mode dontAsk --allowedTools Agent Read Edit Write --no-session-persistence
```

Result: the edit was made, and `modelUsage` lists `claude-haiku-5-5` (1,153 output
tokens, $0.006) next to the Sonnet session ($0.145): the subagent's `model: haiku`
frontmatter is honored. Effort isn't reported per model, so `effort: low` is not
verified by this test.
