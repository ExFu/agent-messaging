---
id: T3-claude-router
plan_kind: thematic
tier: 3
t2_parent: T2-messaging-v1
milestone: M1-first-roundtrip
owner: claude
status: draft
---

# T3 (Claude): the router session that delivers mail to Claude sessions

**Owner: Claude. Codex builds none of this, and it delivers only to Claude sessions.** Date: 3 November 2026. Parent:
[T2-messaging-v1](T2-messaging-v1.md), piece 3. Status: draft, waiting on the T1, the contract and
[T3-claude-mail-tool](T3-claude-mail-tool.md).

## Why

An idle Claude session does nothing until a message arrives in it, so a session cannot watch a mailbox itself. One
long-lived router session watches for every Claude session on the Mac and puts each message into the right one with
`SendMessage` to its `local_…` id.

## What it does

1. **Starts** from a short brief ("Load the agent-mail-router skill and run it") on a cheap model, in any folder. It says
   hello as the router and checks no other router is running.
2. **Waits** on a background command (`watch --for claude --once`) that exits when mail for Claude waits, or after an
   hour so held mail gets another look. Nothing polls in its context.
3. **Routes** each waiting message:
   - Resolves the targets with the shared command (sessions, channel listeners, role holders, the orchestrator
     fallback), keeping only Claude sessions.
   - Checks each target is alive and not archived (`list_sessions`). A dead target goes to the orchestrator instead,
     and the sender is told in the thread.
   - For a message to plain `claude`: the thread first (a reply goes to the session that asked), then presence and
     qualifiers when the content plainly belongs to one session's work, otherwise the orchestrator.
   - Delivers the envelope text unchanged and records `delivered`; records `failed` or `held` when it cannot.
4. **Never** answers a message, does its work, starts sessions, edits files or asks Alastair anything. The orchestrator
   does those.

## Slices

1. The router skill, with the loop and the rules above.
2. A dry run: a fresh subagent follows the skill against a throwaway mailbox, with delivery simulated, covering a
   reply, a channel fan-out, a role, a replacement, a dead session and an unplaced message. Its findings are fixed
   before any real use.
3. A live run in one project with Alastair watching: real deliveries into two Claude sessions and the orchestrator.

The first-pass router skill in `prototype/claude-skills/agent-mail-router/` passed a dry run of the older model (four
messages placed correctly, ten unclear points found and fixed). It needs rewriting for channels and roles.

## Done when

The dry run and the live run route every message as the rules say, no message is delivered twice in normal running,
and the router's own transcript stays at about a line per message.

## Open

- Should the router send Alastair a push notification when mail has been held for a long time (default: no)?
- One router per Mac, or one per project? Proposed: one per Mac, since the mailbox is machine-wide.


## Planning linkage, 4 November 2026

Codex added the missing milestone pointer to M1-first-roundtrip. Ownership and the original brief are unchanged.
Before implementation, Claude should reconcile this brief with the requested contract changes in
[the Codex domain review](../docs/reviews/2026-11-04-codex-domain-review.md) and publish final paths and verification commands.
