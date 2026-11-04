# Real mailbox scheduled nudge — 4 November 2026

Status: implementation prepared; scheduled real-mailbox test pending.

Use the existing authorised test recipient `01a1a78b-7824-7c73-b3dd-9f27bf235db2`, host local. Register it, send the harmless direct request EXFU-REAL-MAIL-002 through tool/mail.py, and let a genuine heartbeat nudge it. The recipient reads, replies and closes the request. Verify the reply and original status through the shared command. A manual nudge is not evidence of the scheduled path.

Record request/reply IDs, scheduler trigger time and observed result below once they exist. Busy, unavailable and offline cases remain untested; no exhaustive test matrix blocks this increment.

## Prepared live run

Request: `20261104T174330.838Z-codex-aa2bf4c8`, sequence 49, published at 17:43:30.838 UTC. The recipient registered itself and was confirmed idle before sending. Router automation: `agent-mail-codex-router`, active every five minutes. Cursor remains zero until the first actual routing run.

## Command checks passed

A throwaway mailbox exercised the exact session command sequence with two Codex identities: future-only attachment excluded old mail; explicit pending catch-up made it visible; read and reply left it open; closed removed it; the reply reached the sender; new excluded the finished recipient; querying at latest returned no messages; detach succeeded. No shared-tool code changed.

The existing real channel handover also verified registration, attachment, catch-up and immediate inbox handling. Scheduled real-mailbox delivery and its reply are still pending.
