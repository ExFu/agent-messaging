---
id: T3-claude-mail-tool
plan_kind: thematic
tier: 3
t2_parent: T2-messaging-v1
milestone: M1-first-roundtrip
owner: claude
status: draft
---

# T3 (Claude): the shared command for the mail files

**Owner: Claude. Codex builds none of this.** Date: 3 November 2026. Parent: [T2-messaging-v1](T2-messaging-v1.md),
piece 2. Status: draft. It waits on the T1 being agreed and the contract (`docs/contract-v1.md`) being written; where
this plan and the contract differ, the contract wins.

Claude proposes to own this because Claude's router and skills need it either way. Codex may call it, or write its own
client against the contract; this plan works for both.

## What it is

One command, `mail.py` (Python 3.9+, standard library only, no install step), that is the only thing either side needs
to read and write `~/.agent-mail/` correctly: atomic writes, sortable ids, the append-only registry, and resolving a
message to its targets. Every command can print JSON, so any agent can use it from a shell.

## Commands

| Group | Commands |
|---|---|
| Identity | `whoami`, `hello` (presence), `who` |
| Channels | `channel create/list/show`, `attach`, `detach` (with `--as` and `--replace` for handing over) |
| Roles | `role claim/release/list` (with `--as` and `--replace`) |
| Messages | `send`, `reply`, `read`, `thread`, `status`, `inbox` |
| Observers | `pending --for <platform>`, `targets <id> --for <platform>`, `mark` (receipts), `watch --once/--follow`, `envelope` (Claude's delivery text) |

## Slices

1. **Messages and receipts:** send, reply, read, inbox, thread, status, mark. Tests: atomic concurrent writes, ids
   sort, replies keep thread and project, bad input refused without writing.
2. **Registry:** channels, attachments, roles, presence, replacements, all as append-only events folded into state.
   Tests: channels say their project and purpose, attaching later does not replay old mail, roles are per project,
   replacement carries undelivered mail.
3. **Observer support:** pending, targets, watch, envelope, the orchestrator fallback and held mail. Tests: each
   platform sees only its own targets, failed delivery stays queued, held mail leaves the queue until something
   changes, unplaced mail waits for an orchestrator.
4. **Ship:** packaged in this project's plugin (see [T3-claude-session-skills](T3-claude-session-skills.md)), with
   `--help` as its reference.

The parked sketch in `prototype/tool/` covers most of slices 1 to 3 in rough form. It is a starting point to rewrite
against the agreed contract, not code to keep as it is.

## Done when

All four slices pass their tests in a throwaway mailbox, the contract's examples round-trip through the command, and
Codex has confirmed it either uses the command or has its own client that reads and writes the same files.

## Open

- If Codex wants to write its own client, the contract needs a shared set of example files both clients test against.
  Claude would write them in slice 1.


## Planning linkage, 4 November 2026

Codex added the missing milestone pointer to M1-first-roundtrip. Ownership and the original brief are unchanged.
Before implementation, Claude should reconcile this brief with the requested contract changes in
[the Codex domain review](../docs/reviews/2026-11-04-codex-domain-review.md) and publish final paths and verification commands.

## First slice, 4 November 2026

Alastair approved a narrow first slice ("Yes, minimum slice"): the command as `tool/mail.py`, manual mode only, on the
real `~/.agent-mail/`. It covers projects, mandates, sessions, channels, attach with qualifiers, catch-up, send, read,
reply and per-recipient marks, with locked, atomic publication and a registry snapshot fixed when each message is sent.
Roles, replacement, rerouting, retries, leases and relay receipts are refused until they are built. Tests:
`python3 -m unittest discover tool/tests`. Report: [docs/reports/2026-11-04-mail-tool-first-slice.md](../docs/reports/2026-11-04-mail-tool-first-slice.md).
The rest of this plan (slices 2 to 4 above, rewritten against the contract) is still to do.
