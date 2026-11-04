---
id: T3-claude-session-skills
plan_kind: thematic
tier: 3
t2_parent: T2-messaging-v1
milestone: M1-first-roundtrip
owner: claude
status: draft
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
