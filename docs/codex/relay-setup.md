# Codex router setup — local prototype

One active heartbeat: `agent-mail-codex-router`, attached to chat `01a1a78b-e940-7ac0-81b1-c4a7909dcb7e`, host local. Created 4 November 2026 at 17:43:08 UTC. Saved configuration was inspected: active, five-minute cadence, correct target chat and repository prompt. No standalone router chat was created.

Prompt source: `codex/templates/relay-prompt.md`. The two currently authorised destinations are this integration chat and test recipient `01a1a78b-7824-7c73-b3dd-9f27bf235db2`. Registration alone does not authorise nudging other chats. Old-chat historic mail may still appear; do not nudge that chat without authorisation or alter its marks.

Initial cursor is zero. The preparatory `new` inspection did not send nudges or advance the cursor. Request `20261104T174330.838Z-codex-aa2bf4c8` (sequence 49) is pending for the genuine scheduled test. No manual nudge was sent for it.

To pause/resume/remove: use automation_update with this automation ID, preserving its other settings. Inspect the tool schema first. To move the router, pause the old heartbeat, bind the user-chosen existing chat and update its target/prompt. Resetting the sequence to zero is safe. No leases or delivery state need recovery. Disable the heartbeat before removing this checkout. App/machine offline behaviour remains untested.

## Faster cadence — 4 November 2026

At Alastair's request, the same heartbeat was updated to every minute. The saved active schedule and target were verified after the update. This is a configured cadence, not a measured latency guarantee.

The local CLI also exposes `codex queue --thread UUID --message TEXT`. A harmless direct wake-up probe to the existing test chat was accepted as queue item `01a1a7ab-6a91-7422-93f7-5a1756e1a836`. Enqueue success alone does not prove the idle desktop chat wakes. The probe explicitly leaves the scheduled mailbox test untouched.

### Direct idle-chat wake-up verified

The queue probe woke the idle test chat and produced turn `01a1a7ab-86c5-7b22-ae8f-ff6a203c30bd`. Its final reply was `EXFU-QUEUE-003 — 2026-11-04 17:46:45 UTC`. This proves the installed local CLI can wake this idle desktop chat, not merely enqueue text. Claude was informed through the real contract channel. Its router has not been changed; busy/offline behaviour is untested. The heartbeat remains active at one minute as the current scheduled route.
