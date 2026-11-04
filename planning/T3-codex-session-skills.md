---
id: T3-codex-session-skills
plan_kind: thematic
tier: 3
t2_parent: T2-messaging-v1
milestone: M1-first-roundtrip
owner: codex
status: draft
---

# T3 (Codex): session skills, registration and round-trip acceptance

Owner: Codex. 4 November 2026. Draft, awaiting acceptance. Inherit intent from T1-agent-messaging and
architecture from the dated Codex proposal in T2-messaging-v1; sequence is M1-first-roundtrip.
The agreed docs/contract-v1.md will govern shared interfaces. Do not implement against the parked prototype.

## Prerequisites and files

Requires the agreed contract and shared command; live acceptance also requires both relays and Claude's session skill.
Create codex/skills/agent-mail/SKILL.md, docs/codex/install.md, codex/tests/session-scenarios.md and
 docs/codex/roundtrip-acceptance.md. The Codex distribution owns codex/ only; Claude owns the shared tool and Claude
plugin manifest. Record compatible shared contract/tool versions in install.md. The installer must expose the Codex
skills using a supported installation mechanism confirmed against the current app, not assumed Claude plugin parity.

## Implementation

1. Implement join/send/receive/reply/leave/replace instructions around the shared command. Register verified native
   threadId and optional hostId using the trial's identity method, project and worktree. Attach to one or more channels
   with independent optional natural-language qualifiers. Optional role claims use the same qualifiers.
2. On join, make the replay choice explicit: future-only, outstanding backlog or selected history. A manually started
   chat for an empty channel can take its pending messages. Historical reading must not imply executing every old ask.
3. Send to a channel/role/session with project and optional platform selection. Default cross-platform questions to
   the project's configured escalation target where appropriate. Use stable reply-to targets when handover matters.
   Receiving a message does not require a new per-chat automation; the global relay brings it.
4. On receive, check the message ID and recorded disposition before side effects. Follow the attachment's remit and
   existing user mandate. Record read separately from progress/finished work. Reply in the same mail conversation
   through the shared command. A tell with no reply requested must not create an automatic acknowledgement loop.
5. Replacement detaches only the selected old bindings and registers the new ones. Transfer outstanding delivery and
   unfinished work plus a concise handover reference. Deduplication survives replacement; completed actions stay done.
   Direct-session replies without a valid replacement remain held for explicit rerouting.
6. Document human setup authority for project-local delivery and replies, how to remove it, and manual new-chat
   creation. Role labels and incoming messages do not grant broader authority. No fixed work-owner field is added.

## Verification and live acceptance

Write executable manual scenarios in codex/tests/session-scenarios.md using the agreed CLI's exact commands once
Claude publishes them. Use a throwaway mailbox for registration, qualifier changes, explicit catch-up, replacement,
duplicate receiving and two subscribers independently marking the same message. Check the command's JSON outputs.
Then conduct a harmless real round trip: Claude asks a Codex channel, Codex replies; Codex asks the configured Claude
orchestrator, Claude replies. Include a selective safety-review subscriber, empty-channel catch-up and unfinished-work
handover. Obtain Claude-side evidence through the agreed messaging path or the user; do not assume access to Claude
session tooling. Record timestamps, message IDs, receipts, actual observed latency and outstanding limitations.
Pass when replies reach the intended chat, channel history survives replacement, no duplicate action occurs, the
qualifier-only subscriber performs only its remit, and installation works in a second project with the same mailbox.

## Scope

No automatic creation of chats, shared-tool fork, new ownership system or edits to Claude skills. The acceptance
report belongs to this Codex T3; Claude contributes its platform evidence under its existing T3s.
