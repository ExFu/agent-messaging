---
id: T3-codex-capability-trial
plan_kind: thematic
tier: 3
t2_parent: T2-messaging-v1
milestone: M1-first-roundtrip
owner: codex
status: draft
---

# T3 (Codex): prove scheduled chat delivery

Owner: Codex. 4 November 2026. Draft, awaiting acceptance. Inherit intent from T1-agent-messaging and
architecture from the dated Codex proposal in T2-messaging-v1; sequence is M1-first-roundtrip.
The agreed docs/contract-v1.md will govern shared interfaces. Do not implement against the parked prototype.

## Inputs and output

Read docs/reviews/2026-11-04-codex-domain-review.md. Create docs/codex/capability-trial.md with the actual desktop
version if exposed, tool schemas/date, verified identity source, test chat/host IDs, automation ID, timestamps and outcomes.
This trial needs no shared command. Use a throwaway mailbox under the system temporary directory and harmless numbered
messages. Use manually opened test chats and the user's explicit mandate for test delivery; do not message unrelated chats.

## Procedure

1. Discover automation_update, list_threads, read_thread, send_message_to_thread and wait_threads from the live tools.
   Establish the current relay and recipient chat identities from trusted app/runtime evidence. If self-identification
   is not exposed, document a one-time manual binding. Do not use titles as stable identifiers.
2. Create one heartbeat attached to the test relay through automation_update, requesting every five minutes. Inspect
   the returned saved schedule. If unsupported, record the actual limitation and stop the dependent relay build; do
   not replace it silently with a different scheduler or claim support from schema availability alone.
3. Let a genuine scheduled wake-up read one numbered test message and use send_message_to_thread to deliver it to
   the authorised idle recipient. Confirm arrival and a reply in the test mailbox. Record tool availability during
   that scheduled run, filesystem access and what the send result actually guarantees.
4. Repeat with the destination busy, then with an invalid/archived destination. Determine queuing, steering, rejection
   and approval behaviour from observations. Test a repeated polling run and an unchanged inbox. Confirm no duplicate
   handling and no routine user notification. Inspect whether overlapping runs occur; never infer serial execution.
5. Record behaviour while the app or machine is unavailable using a user-coordinated test if needed. If not tested,
   label it unverified and document the operational constraint. Pause/remove the temporary heartbeat afterwards.

## Pass criteria and dependencies

At least one real scheduled run can read the mailbox and deliver to the authorised existing chat. The saved cadence
is verified; busy handling and failure behaviour are recorded. The receiving chat can reply without manually polling.
A tool schema alone is not a pass. Any unsupported critical capability becomes a concrete limitation for review.
The trial can follow acceptance independently of Claude's command; T3-codex-relay depends on its outcome.

## Scope

No production messages, no persistent watcher daemon, no external desktop database writes, no new sessions created
by the relay. Do not modify Claude's code or select a model without the user's instruction.
