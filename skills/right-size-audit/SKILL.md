---
name: right-size-audit
description: Show where this project's Claude Code spend went, from the session transcripts on disk, and which change would cut it most. Use when the user asks where their tokens or money go, why a session was expensive, whether a cost-saving skill or setting is worth it, or before changing the project's default model.
disable-model-invocation: true
---

Every cost-saving tip works on one slice of the bill: shorter replies only touch output tokens, a cheaper model touches everything, a smaller context touches input and cache. Which slice is big differs per project. This skill measures it from the transcripts Claude Code already keeps, so the advice rests on the user's own numbers instead of a headline percentage.

The audit reads local files only. It makes no model calls and sends nothing anywhere.

## Steps

1. **Run the audit.** `python <this folder>/scripts/audit.py` covers the current project over the last 30 days. Use `--days N` for another window, `--project PATH` for another project, `--all` for every project, `--json` to work with the numbers. It needs the `right-size` skill installed next to this one (it reads the prices in `../right-size/harnesses/claude-code.yaml`); if it says so, tell the user to install it and stop.

2. **Read it to the user**, briefly, in this order:
   - the total and the model that dominates it;
   - the token-kind split, and what it means for the user's question: output share is the most that reply-shortening can save; input and cache share is where model choice and context size act;
   - each finding the script printed, with its number.

3. **Recommend at most two changes**, the ones the numbers point to, biggest first:
   - Sessions that edited little but ran above the standard tier → a `standard` default with escalation on failure: offer the `right-size-defaults` skill.
   - Model switches inside conversations → switch at the start of a session, or change effort instead; effort changes keep the cache.
   - Subagents on the top model doing reading → give them the `scout` tier: offer `right-size-setup`.
   - Cache writes a large share → long sessions that keep growing; start a fresh session per task.
   - Output a small share → say plainly that tools which shorten replies can't save much here.

## Caveats to state when they apply

- List prices are what the tokens are worth at API rates. On a subscription plan they show relative weight, not money spent.
- "The same tokens on a cheaper model" is a ceiling on the saving: a smaller model can need more turns. right-size's benchmark measures the real effect on solved tasks.
- A model without a price entry is listed, not counted: tell the user to add it to `harnesses/claude-code.yaml` in the right-size skill.
