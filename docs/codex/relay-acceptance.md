# Real mailbox scheduled nudge — 4 November 2026

Status: implementation prepared; scheduled real-mailbox test pending.

Use the existing authorised test recipient `01a1a78b-7824-7c73-b3dd-9f27bf235db2`, host local. Register it, send the harmless direct request EXFU-REAL-MAIL-002 through tool/mail.py, and let a genuine heartbeat nudge it. The recipient reads, replies and closes the request. Verify the reply and original status through the shared command. A manual nudge is not evidence of the scheduled path.

Record request/reply IDs, scheduler trigger time and observed result below once they exist. Busy, unavailable and offline cases remain untested; no exhaustive test matrix blocks this increment.

## Prepared live run

Request: `20261104T174330.838Z-codex-aa2bf4c8`, sequence 49, published at 17:43:30.838 UTC. The recipient registered itself and was confirmed idle before sending. Router automation: `agent-mail-codex-router`, active every five minutes. Cursor remains zero until the first actual routing run.

## Command checks passed

A throwaway mailbox exercised the exact session command sequence with two Codex identities: future-only attachment excluded old mail; explicit pending catch-up made it visible; read and reply left it open; closed removed it; the reply reached the sender; new excluded the finished recipient; querying at latest returned no messages; detach succeeded. No shared-tool code changed.

The existing real channel handover also verified registration, attachment, catch-up and immediate inbox handling. Scheduled real-mailbox delivery and its reply are still pending.

## Scheduled path passed — 17:53 UTC

The genuine heartbeat trigger at 17:51:04.617 UTC called send_message_to_thread with only the inbox nudge for the authorised test recipient. The recipient reported receipt at 17:51:52 UTC and published reply `20261104T175204.819Z-codex-f929af6a` at 17:52:04.819 UTC. The shared tool reports the original request as read, answered and closed. The reply reached this integration chat and was verified through thread/status commands.

This establishes the scheduled real-mailbox round trip. Receipt was about 47 seconds after this heartbeat trigger. The request had waited since 17:43 while setup and user conversation continued; neither number is a steady-state latency promise. Busy, unavailable and offline delivery remain untested.

Alastair subsequently approved a single Claude-hosted router for both platforms, conditional on it working. The one-minute heartbeat remains a fallback until that separate route is verified. Its success must use a distinct test and is not established by this result.
