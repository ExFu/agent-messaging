---
id: T3-claude-router
plan_kind: thematic
tier: 3
t2_parent: T2-messaging-v1
milestone: M1-first-roundtrip
owner: claude
status: completed
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

## First slice, 4 November 2026

Alastair: "Start them now" (not waiting for Codex's delivery trial). Built against contract draft 3, with no roles yet:
- **The skill:** [plugin/agent-mail/skills/agent-mail-router/SKILL.md](../plugin/agent-mail/skills/agent-mail-router/SKILL.md).
- **Command support** in `tool/mail.py`:
  - `lease` (acquire, renew and release, with a generation token);
  - `pending --for claude`, a queue of decide, deliver, reconcile, retry, exhaust and unplaced items;
  - `watch`, which blocks in the background until there is work;
  - `relay`, which writes the router's receipts and checks the lease;
  - `envelope`, the exact delivery text.

Liveness uses `get_session`, and delivery uses `SendMessage` to the `local_…` id. Changes from the brief above, to fit
the contract:
- A dead target is held with its reason, not sent to an orchestrator, because there is no orchestrator role yet.
- Bare `claude` mail goes only to the Claude session already in the thread. Anything else is held for placing by hand.
- Escalation notices are not built. The router says so in one line of its own transcript.

Tests: `python3 -m unittest discover tool/tests`. Slice 2 (the dry run) is running. Slice 3 (the live run) comes next.

## Simplified to nudging, 4 November 2026

Under [contract v2](../docs/contract-v2.md), the router only nudges each Claude session that has new mail: "You have
new agent mail: run mail.py inbox". It keeps one number (the latest message seq it has handled) and no records. It
takes no lease, and makes no routing decisions. The command's `lease`, `pending`, `relay` and `envelope` are gone.
`new --for claude --since <seq>` and `watch --since <seq>` replace them. The dry run above tested the older delivering
design, so the nudging router still needs its live run.

## One router for both platforms, 4 November 2026

Alastair approved one router, in Claude, nudging both platforms, if it works. The router runs `new --for all` and
nudges Codex chats with `codex queue --thread <id> --message <text>`. Test EXFU-ROUTER-CLAUDE-001 woke an idle Codex
test chat with no other help. The chat read the message, then paused to check whether replying was in its brief, and
replied once that was clarified. Codex keeps its one-minute heartbeat as a fallback until the two sides agree to
retire it.


## Done when, restated for contract v2 (4 November 2026)

The criteria above were written for contract v1: roles, replacement records, relay receipts, a five-minute target.
v2 dropped those. Alastair: "Go ahead" (4 November 2026), on restating the criteria for v2 and closing.

Met: the live router nudges sessions on both platforms, with about one line of transcript per nudge. Results:
- message 28 to Claude, nudged;
- message 77 to a Codex chat, which woke on its own;
- messages to Codex alone, or between Codex chats, correctly not nudged.

A repeat nudge is harmless, and none was needed in normal running.
