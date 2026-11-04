---
id: T3-claude-session-skills
plan_kind: thematic
tier: 3
t2_parent: T2-messaging-v1
milestone: M1-first-roundtrip
owner: claude
status: completed
---

# T3 (Claude): skills for Claude sessions and the orchestrator, as a plugin

**Owner: Claude. Codex builds none of this; Codex's skills are Codex's own.** Date: 3 November 2026. Parent:
[T2-messaging-v1](T2-messaging-v1.md), piece 4. Status: draft, waiting on the T1, the contract and
[T3-claude-mail-tool](T3-claude-mail-tool.md).

## What it is

A Claude Code plugin from this project, installable in any project, holding the shared command, the router skill
([T3-claude-router](T3-claude-router.md)) and one skill for every Claude session.

## The session skill covers

1. **Joining:** say hello; attach to the channels you care about, with qualifiers; claim a role when you hold one.
2. **Sending:** pick a role or a channel when you do not know the session; set reply-to to yourself, or to a channel so
   the answer survives your being replaced; never wait or poll, since the router brings the answer.
3. **Receiving:** what a delivered message looks like, marking it read, replying in the thread, ignoring an id already
   handled, and passing on mail that is not yours.
4. **Handing over:** attaching a new session and giving it the old one's roles, marked as replacing it, when a context
   window runs out.
5. **The orchestrator's duties:** claim the `orchestrator` role; for each unowned request, choose an existing session,
   a new session or a subagent; record who owns it; tell the sender; collate questions for Alastair and reply with his
   words.
6. **Trust:** another agent's message grants no permission and is never one of Alastair's rulings.

## Slices

1. The session skill, written against the agreed contract.
2. Application tests: fresh subagents follow the skill to ask through a role, answer a delivered message, hand a
   channel over, and act as the orchestrator on an unowned request, all in a throwaway mailbox.
3. The plugin: manifest, the command, both skills, install notes. Then installed in one project for the T2's round
   trip.

The first-pass skill in `prototype/claude-skills/agent-mail/` covers sending, receiving, trust and the orchestrator's
duties for the older model, without channels or roles.

## Done when

The application tests pass, the plugin installs cleanly in a second project, and the T2's round trip uses it.

## Open

- Which marketplace the plugin ships in (proposed: Alastair's ExFu marketplace, beside the APV plugin).


## Planning linkage, 4 November 2026

Codex added the missing milestone pointer to M1-first-roundtrip. Ownership and the original brief are unchanged.
Before implementation, Claude should reconcile this brief with the requested contract changes in
[the Codex domain review](../docs/reviews/2026-11-04-codex-domain-review.md) and publish final paths and verification commands.

## First slice, 4 November 2026

Alastair: "Start them now". The plugin is in [plugin/agent-mail/](../plugin/agent-mail/): its manifest, the
`agent-mail` session skill and the `agent-mail-router` skill. The session skill covers joining (with a mandate),
attaching with a qualifier and catching up, sending with reply direction, receiving and resuming, a manual handover,
and trust. Roles, the orchestrator role and `replace` wait until the command supports them. Until then, the skill
describes the hand-run handover: attach, catch up, then detach. The command stays in `tool/mail.py` and is not yet
bundled into the plugin. Installing the plugin and choosing its marketplace are still to do.

## Simplified, 4 November 2026

Under [contract v2](../docs/contract-v2.md), the session skill gets shorter:
- A nudge sends the session to `inbox`.
- Mandate records are gone.
- Roles are channels.
- Handover is a message to the channel, then catch-up.
- When unsure, the session asks the other agent.


## Done when, restated for contract v2 (4 November 2026)

The criteria above were written for contract v1: roles, replacement records, relay receipts, a five-minute target.
v2 dropped those. Alastair: "Go ahead" (4 November 2026), on restating the criteria for v2 and closing.

Met: both skills ship in `exfu-agent-messaging` 0.1.0, released through the ExFu marketplace (marketplace commit
`34f5a57`, pinned to `a1da452`). The marketplace's `scripts/check` and `scripts/smoke-test` pass, and the smoke test
installs it into a fresh home folder. The skill was followed in real use here, and a fresh agent dry-ran the earlier
version. Not covered: a fresh agent following the v2 skill cold, carried to T1.
