# Scheduled delivery evidence — 4 November 2026

The prior Codex session proved a genuine five-minute heartbeat could call the app messaging tool and wake an existing idle chat. The heartbeat arrived at 17:14:04.415 UTC. Dispatch began at 17:14:29.625 UTC and the recipient recorded receipt at 17:14:45.617 UTC. That is about 41 seconds from scheduled wake-up to receipt, not a general latency guarantee.

Recipient: `01a1a78b-7824-7c73-b3dd-9f27bf235db2`, host `local`. Identity came from CODEX_THREAD_ID. The temporary automation was removed after the test. Desktop version and temporary automation ID were not preserved in the exported evidence; do not infer them.

Original JSON evidence is copied unchanged into `evidence/scheduled-trial/`. The send tool returned a thread ID; receipt was established separately from the recipient's file and completed turn. This was a transport test, not real-mailbox routing. Busy recipients, unavailable destinations and app/machine offline remain untested. The real-mailbox follow-up is recorded in relay-acceptance.md.
