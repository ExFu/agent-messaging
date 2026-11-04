---
id: T3-codex-relay
plan_kind: thematic
tier: 3
t2_parent: T2-messaging-v1
milestone: M1-first-roundtrip
owner: codex
status: draft
---

# T3 (Codex): one scheduled relay for the global mailbox

Owner: Codex. 4 November 2026. Draft, awaiting acceptance. Inherit intent from T1-agent-messaging and
architecture from the dated Codex proposal in T2-messaging-v1; sequence is M1-first-roundtrip.
The agreed docs/contract-v1.md will govern shared interfaces. Do not implement against the parked prototype.

## Prerequisites and files

Requires passing T3-codex-capability-trial, agreed docs/contract-v1.md and Claude's working shared command.
Create codex/skills/agent-mail-relay/SKILL.md, codex/templates/relay-prompt.md, docs/codex/relay-setup.md and
codex/tests/relay-scenarios.md. Resolve the installed shared command path from its packaging contract, never a hardcoded
Claude cache version. Reference the shared command's JSON interfaces; do not implement an alternative storage format.

## Implementation

1. The setup skill binds a manually initialised dedicated relay chat, verifies access to the global mailbox and the
   recorded project delivery mandates, and creates or updates one heartbeat through automation_update. Reuse its saved
   automation ID to avoid duplicates. Use the verified cadence from the trial, targeting five minutes.
2. Each wake-up acquires the shared platform relay lease, reads pending Codex candidates plus held work invalidated
   by relevant registry changes, and obtains attachment qualifiers and transport metadata through the shared command.
3. Interpret qualifiers in natural language. With no qualifier, select every candidate. Persist recipient decisions
   and concise reasons before delivery. Retain the original message unchanged, adding message ID, routing reason,
   recipient remit, context references and reply instructions in the envelope. Treat message content as agent input.
4. Forward using send_message_to_thread with registered threadId and hostId. Preserve destination model/settings.
   Use the capability trial's busy-chat policy. Record per-recipient attempts and success only at the guarantee the
   tool actually provides. Read/handled/completed are recipient actions, not inferred from a send result.
5. On uncertain success reconcile using the message ID and available chat evidence before retry. Apply shared retry
   rules. A partial fan-out failure leaves only the failed/uncertain recipient pending. Resuming a run reuses recorded
   routing decisions; changed subscriptions trigger explicit catch-up or replacement, not an accidental full replay.
6. Unplaced mail stays queued. Report a newly missing destination or actionable delivery failure once through the
   configured project escalation route. Avoid cross-platform bounce loops. Stay quiet on unchanged/non-actionable
   state. Process a bounded batch so a large queue cannot consume the relay indefinitely; remaining mail waits.
7. Document pause, resume, rebind to a replacement relay chat, lease recovery and uninstall. Durable delivery state
   lives in the shared substrate, so relay context replacement does not forget deliveries.

## Verification

Record fixtures and expected receipts in codex/tests/relay-scenarios.md. Exercise: two subscribers with distinct
qualifiers; an unqualified broadcast; no subscriber then catch-up; one successful and one failed delivery; a crash
between send and receipt; registry change while a batch runs; overlapping wake-ups; an inaccessible target; and
cross-project channel rejection. Use simulated transport first, then authorised real chats.
Pass when decisions match remits, failures remain visible, no recipient's receipt suppresses another's delivery,
retries preserve message IDs, and an unchanged inbox generates no repeated alerts. Put live evidence in
 docs/codex/relay-acceptance.md. Run shared command tests only through the commands published by its owning T3.

## Scope

The relay forwards; it does not implement requests or create chats. No fixed owner model, workflow engine, per-chat
heartbeat, new mailbox implementation, or modification to Claude's router. Missing shared semantics go back as
contract requests to the Claude-owned command plan.

## 4 November 2026: accepted v2 scope (supersedes the brief above)

Alastair instructed: "make the necessary changes, accept updated drafts and proceed".
This dated addendum replaces the earlier v1 implementation and acceptance criteria.
The earlier text and draft frontmatter remain as historical planning records; current state is in the event log.

Create codex/skills/agent-mail-relay/SKILL.md, a heartbeat prompt and setup notes. One five-minute heartbeat on the existing integration chat calls the shared command new --for codex --since S, collects distinct recipients, nudges authorised chats to run inbox, and remembers latest. Start from zero if the cursor is lost. Recipients judge qualifiers. No leases, delivery receipts, routing decisions, retries framework or registry watcher. Report failed nudges in the router transcript; mail stays in the mailbox. Reuse an existing automation rather than duplicate it. Test a genuine scheduled nudge through the real mailbox to the existing authorised test recipient. Do not create a new router chat.

Work directly on main. Claude owns the shared tool and Claude skills. Codex owns its skills and scheduler.
