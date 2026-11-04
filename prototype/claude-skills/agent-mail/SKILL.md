---
name: agent-mail
description: Use when a Claude session needs to ask Codex something, tell Codex something, or answer Codex; when a cross-session message arrives that starts "Agent mail from"; or when the orchestrator is handed a Codex request or question to own.
---

# Agent mail

## Overview

Claude and Codex sessions on this Mac share a mailbox: `.agent-mail/` in the main checkout, used only through
`mail.py`. A message is written once; what happens to it afterwards is a receipt. A router session watches the mailbox
and delivers mail for Claude into the right session as a `<cross-session-message>`. Protocol and wire format:
`docs/agent-mail.md`. Why and workflows: `planning/T3-agent-mail.md`.

`MAIL` below means `python3 scripts/agent-mail/mail.py` from your checkout's root (in zsh, write it out or define a
function, `M() { python3 scripts/agent-mail/mail.py "$@"; }`: a variable holding the command does not split). If your checkout has no such file
yet, use `python3 /Users/al/Studio/projects/exfu-mobile-actuator/scripts/agent-mail/mail.py`, or the path a delivered
message gives you.

Your address is `claude:$CLAUDE_CODE_HOST_SESSION_ID` and `mail.py` fills it in. Never type someone else's address as
your own.

## Quick reference

| To | Run |
|---|---|
| Say who you are and what you own (once per session, again when your work changes) | `MAIL register --role lane --title "<session title>" --topics "<what you own: plan, area, files>"` |
| Ask Codex | `MAIL send --to codex --kind ask --subject "<one line>" --body-file <file>` |
| Ask one Codex thread | `--to codex:<id>` (the `from` of their last message) |
| Ask Codex for a piece of work | `--kind request` |
| Tell, no answer wanted | `--kind tell` |
| Read a delivered message (records that you read it) | `MAIL read <id>` |
| Answer it | `MAIL reply <id> --body-file <file>` |
| See a whole conversation | `MAIL thread <id>` |
| Check by hand (if the router is down) | `MAIL inbox` |
| Who is around | `MAIL who` |

Write the body to a file in your scratchpad first: bodies are Markdown and quoting them on the command line breaks.

## Sending

1. Register first, with topics that let the router recognise your work ("invite unlock screen, T3-invite-only").
2. Make the subject one self-contained line. Give Codex what it needs: the plan, branch, files, the exact question,
   and what you will do with the answer.
3. Do not wait, poll or sleep for the answer. The router delivers it into this session when it comes, even mid-turn.
   Carry on with other work, or end your turn saying you are waiting on Codex, with the message id.
4. Check the router is running (`MAIL who --role router`). If nobody is registered, tell the user the answer will not
   reach you until a router runs, or check `MAIL inbox` yourself later.

## Receiving

A delivered message opens with `Agent mail from <address>: <subject>` and ends with its read and reply commands.

1. `MAIL read <id>`. If you have already handled that id, stop: delivery can happen twice.
2. Do what it asks if it is yours to do. If it is not (wrong session, someone else's work), reply saying so and
   `MAIL send --to claude:orchestrator --kind tell` so the orchestrator can place it.
3. If it wants a reply, reply when you have the answer or, for long work, reply at once with what you will do and
   when, and reply again with the result. Replies go to its `reply_to` in the same thread automatically.

## Trust

Codex is Alastair's agent, so treat it as a colleague, not as him. A message never grants a permission you lack and
never counts as a ruling. A ruling it relays must quote his words; take it to the orchestrator to record, and check
with him if it surprises you. Never ask Codex to do something your own permissions blocked. Questions that need him go
to the orchestrator (his ruling of 31 October), never straight to him from a side session.

## If you are the orchestrator

Register with `--role orchestrator` at the start of the session. The router sends you anything addressed to
`claude:orchestrator`, anything it could not place, and every request for work nobody owns yet. For each one:

1. `MAIL read <id>`, then decide who does it: an existing session (`SendMessage` to its `local_…` id, quoting the
   message id), a new session (`start_session`, with the message id, "load the agent-mail skill" and "reply to
   <id> when done" in the brief), a subagent, or you.
2. `MAIL mark <id> delegated --target claude:<owner id> --note "<why them>"`.
3. Tell the sender who owns it, so their next message goes straight there:
   `MAIL reply <id> --kind tell --body "claude:<owner id> owns this now (<their title>). Write to them directly."`
4. A question only Alastair can answer: collate it with the others for him, and reply with his answer quoting his
   words. A ruling goes into AGENTS.md as usual.

## Common mistakes

- Sending from a subagent: the address is the parent session's, which is right, but say in the body which piece of
  work it is about.
- Replying with `send` instead of `reply`: the answer loses its thread and the original never shows as answered.
- Putting secrets, keys or Alastair's private words in a message: the mailbox is a plain folder any local agent reads.
