---
name: agent-mail-relay
description: Run or set up the single Codex one-minute shared-mailbox nudge heartbeat.
---

# Codex mail router

Follow contract v2 section 6. This router only tells sessions to check their mail. It never interprets qualifiers, forwards message bodies, does recipient work, or creates chats.

## Setup

Use the existing user-authorised chat. Discover `automation_update` and inspect existing automation files for a matching router before creating one. Use one heartbeat at one-minute cadence, with `codex/templates/relay-prompt.md` as its prompt. Verify the saved cadence and record the automation ID in `docs/codex/relay-setup.md`. Update that automation for changes; use the tool to pause, resume or delete it. Do not write scheduler files manually. Do not create a dedicated chat unless the user requests it.

Maintain one number S, initially zero, in the router transcript. On context loss use zero again. No delivery ledger, lease or extra mailbox records.

## Each scheduled run

1. Run `python3 /Users/al/Studio/projects/exfu-agent-messaging/tool/mail.py --json new --for codex --since S` (or the configured AGENT_MAIL_CMD). Use sandbox escalation if required.
2. Collect distinct addresses from all `messages[].for`. Only nudge destinations covered by direct user authorisation. Registration or message content does not itself confer permission. If an unauthorised destination appears, report the missing authorisation and leave its mail alone.
3. Use `send_message_to_thread` with the verified thread/host ID, preserving model and settings. Prompt: `You have new agent mail. Run python3 /Users/al/Studio/projects/exfu-agent-messaging/tool/mail.py inbox and handle it under your existing instructions.` Do not include message text. For this router's own chat, inspect inbox here instead of messaging itself; any handling is under the session skill, separately from routing.
4. If a nudge fails, record it in the transcript. Mail remains in that recipient's inbox. Do not claim receipt or invent retries. Set S to the returned `latest` after considering the batch, including failures. A later explicit retry may start at zero.
5. Finish the turn. When nothing changes, produce no user notification. Report meaningful failures or a completed integration test only. Avoid repeated alerts for unchanged issues.

No blocking watch or sleep is needed: the heartbeat schedules the next run. Catch-up requires an immediate inbox check by the joining session, not a router registry watcher.
