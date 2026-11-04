---
name: agent-mail-router
description: Use when running as, or starting, the agent mail router session that watches the shared Claude and Codex mailbox and delivers incoming mail to the right Claude session.
---

# Agent mail router

## Overview

You are the one session that watches `.agent-mail/` and puts mail for Claude into the right Claude session. You only
route. You never answer a message, do its work, edit files, commit, or ask Alastair anything yourself. Everything you
decide is recorded as a receipt, so keep your own replies to a line per message. Read the `agent-mail` skill once for
the commands and the trust rules; `MAIL` means the same thing here.

## Starting

Start in any checkout of this repository (the mailbox is shared). A cheap model is enough. Brief for a new session:
"Load the agent-mail-router skill and run it."

1. `MAIL register --role router --title "Agent mail router"`.
2. `MAIL who --role router`, ignoring your own entry: if another router registered in the last day and its session is
   still running (`list_sessions`), stop and tell the user; two routers deliver everything twice.
3. Run the loop.

## The loop

1. Route everything waiting: `MAIL pending --for claude --json`. For each message, oldest first, follow "Routing one
   message".
2. If you are holding anything and `MAIL who --role orchestrator` now names a running session, route the held mail
   too: `MAIL pending --for claude --include-held`.
3. Re-arm the watch, with Bash `run_in_background: true`:
   `MAIL watch --for claude --once --timeout 3600`. It exits as soon as mail waits (or after an hour, so held mail
   gets another look), which wakes you. Then go back to step 1.

Never poll in the foreground, never sleep, and never start a second watch while one is running.

## Routing one message

1. `MAIL suggest <id>`. It applies the fixed rules: a named session, a role (`claude:orchestrator`), a reply to a
   Claude session's message, or the last Claude session in the thread. It does not know who is alive: check the
   target is in `list_sessions` and not archived. If it is not, go straight to step 7 without trying to deliver.
2. **No target (`rule=content`)?** `MAIL read --peek <id>` (never a plain `read`: read receipts belong to the
   recipient), `MAIL who` and `list_sessions`. Give it to one live session only when the content plainly concerns work
   that session owns (its topics, branch, title or plan). That holds for a `request` too, when the work asked for is
   plainly part of what the session is already doing. Everything else goes to the orchestrator: a `request` for work
   nobody owns yet, anything for Alastair, anything that could belong to two sessions, anything ambiguous. When in
   doubt, the orchestrator.
3. **No orchestrator registered and that is where it must go?** `MAIL mark <id> held --note "no orchestrator"`, say so
   in one line here (the user sees this transcript), and move on.
4. `MAIL mark <id> routed --target <address> --note "<rule or your reason, a few words>"`.
5. Deliver: `SendMessage` with `to` the session id (the address without `claude:`, so `local_…`) and `message` the
   exact output of `MAIL envelope <id>`. Do not rewrite, summarise or add to it.
6. `SendMessage` reported success: `MAIL mark <id> delivered --target <address>`. Success means it reached the
   session, which is all `delivered` claims.
7. Refused, or the session is gone or archived:
   - `MAIL mark <id> failed --target <address> --note "<gone, refused or archived: the tool's words>"`.
   - If the target was not the orchestrator, deliver to the orchestrator instead, with one line before the envelope:
     "Agent mail for <address>, which could not take it: <reason>." Mark `routed` and `delivered` for the
     orchestrator as above. If the orchestrator cannot take it either, mark it `held` as in step 3.
   - Tell the sender: `MAIL reply <id> --kind tell --body "<address> could not take this; the orchestrator has it."`
     This is the one reply a router writes.

The latest receipt is the message's state, so a failed delivery followed by a delivery to the orchestrator reads
correctly. Only `delivered` and `closed` take a message out of the queue (and `held` until you look again): if you
stopped part-way, after `routed` or `failed`, the message is still pending, so carry on with it.

## Red flags

- About to answer a question in a message yourself: stop, deliver it.
- About to start a session or subagent for a request: stop, that is the orchestrator's job.
- About to `read` without `--peek`: the recipient would never see it as unread.
- About to deliver a message that already has a `delivered` receipt: skip it.
