---
id: T3-agent-mail
plan_kind: thematic
tier: 3
status: draft
---

# T3: agent mail (Claude and Codex talking to each other)

Date: 3 November 2026. Status: draft for Alastair's acceptance. Tooling for the agents, not the product, so it has no
product T2 or milestone. The wire format and commands are in [docs/agent-mail.md](../docs/agent-mail.md); this plan
holds the why, the domain model, the workflows, the slices and the open questions.

## Why

Alastair, 3 November 2026: "I want to create a skill(s) that lets you and Codex chat with each other. I imagine some
shared messaging substrate in the project that both Claude and Codex have read-write access to." And: "On the Claude
side, I'd also want to start a session in the current project that watches for messages incoming from Codex, and sends
them to the relevant Claude session. Sessions asking for a response should therefore provide a session id so that this
observer session can route appropriately. If Codex messages without a target session Id, then the observer needs to
work out which session to send it to based on the content. I typically run a main orchestrator session as well in
Claude. If in doubt, or if the message asks for some particular piece of work that is as-yet unorchestrated, then it's
the orchestrators job to plan and run that work by farming to appropriate sub-session, sub-agents, and creating new ones
if necessary."

Today Codex and Claude only meet through files, plans and handover documents, with Alastair carrying questions between
them by hand. Codex owns the look and Claude builds function (the reusable components ruling), so they ask each other
things all the time. A shared mailbox lets them ask directly, and the orchestrator ruling of 31 October ("questions go
through the orchestrator") still holds: anything that needs Alastair goes to the Claude orchestrator, which asks him.

## Design choices

1. **Files on the Mac, not a service.** Both agents run on the same Mac and both can run shell commands, so the
   substrate is a folder of small JSON files plus one stdlib Python command, `scripts/agent-mail/mail.py`, that both
   sides use. No server, no network, no new accounts.
2. **One folder for every checkout.** The folder is `.agent-mail/` in the main checkout, found through git's common
   directory, so every Claude worktree and any Codex worktree of this repository share it. It is gitignored. The
   environment variable `AGENT_MAIL_DIR` overrides it (for tests, or if Codex's sandbox needs another place).
3. **Immutable messages, append-only receipts.** A message is written once and never changed. Everything that happens
   to it afterwards (routed, delivered, read, answered, closed, failed) is a new receipt file beside it. Two agents
   writing at the same moment can never clobber each other, and the history of a message is always readable. Writes are
   atomic (write to a temporary file, then rename).
4. **Addresses name a platform and, when known, a session.** `claude:local_<uuid>` is one Claude desktop session;
   `claude:orchestrator` is whichever session registered as the orchestrator; bare `claude` means "Claude, you work out
   who". The same shape works for Codex (`codex:<thread>`, `codex`), whose ids are the Codex side's to choose.
5. **Every sender says where answers go.** `reply_to` defaults to the sender's own address. A Claude session's address
   comes from `$CLAUDE_CODE_HOST_SESSION_ID`, which the desktop app sets in every session, so a session never has to be
   told its own id.
6. **Claude sessions cannot watch; one router watches for them.** An idle Claude session does nothing until a message
   arrives, so a mailbox alone would never wake it. One long-lived router session watches the folder with a background
   command that exits when mail is waiting, then delivers each message into the right session with `SendMessage` to its
   `local_…` id. The router only routes. It never answers or does the work, which keeps it cheap (a Sonnet-class model
   is enough) and its context small.
7. **The orchestrator owns anything unowned.** When the router cannot tell who should have a message, or the message
   asks for work nobody is doing yet, it goes to the orchestrator, which plans it and hands it to an existing session, a
   new session or a subagent, then tells the sender who now owns it, so the next message can be addressed directly.

## Domain model

| Thing | What it is | Where it lives |
|---|---|---|
| **Address** | `<platform>[:<id or role>]`. Platforms: `claude`, `codex`. Ids are session ids (`local_…` for Claude). Roles: `orchestrator`, `router`. | inside messages and directory entries |
| **Participant** | A session that can send and receive: its address, role (`orchestrator`, `router`, `lane` or `side`), title, branch, worktree, and a line of what it owns ("topics"). Written by the session itself, refreshed whenever it registers again. | `directory/<platform>__<id>.json` |
| **Message** | One immutable note: id, thread, in_reply_to, from, to, reply_to, kind, subject, body (Markdown), context (branch, files, plan, APV item), created_at. | `messages/<id>.json` |
| **Kind** | `ask` (a question; wants a reply), `request` (asks for a piece of work; wants a reply saying who owns it and, later, the result), `tell` (a notice; no reply wanted), `reply` (answers an earlier message). | in the message |
| **Thread** | Every message in a conversation shares the id of the message that opened it. A reply inherits its parent's thread. | in the message |
| **Receipt** | One event about one message: `routed` (the router chose a target, with its reason), `delivered` (put into a session), `read`, `answered` (with the reply's id), `delegated` (the orchestrator handed it on, naming the owner), `closed` (nothing more to do), `failed` (could not be delivered, with why). | `receipts/<message id>/<time>-<event>-<random>.json` |
| **Status** | Not stored: the latest receipt says where a message stands. A message to Claude with no `delivered` or `closed` receipt, and not held, is in the router's queue. | derived |

Message ids sort by time: `20261103T160512123Z-codex-7f3a`. A message to another platform is "unread" for its reader
until that reader writes a `read` receipt.

## Workflows

### W1. A Claude session asks Codex something

1. The session runs `mail.py send --to codex --kind ask --subject … --body-file …`. `from` and `reply_to` are filled
   in from `$CLAUDE_CODE_HOST_SESSION_ID`; context (branch, worktree) from git.
2. The Codex side picks it up (how is the Codex side's design; see the open questions) and answers with
   `mail.py reply <id>`, which addresses the reply to the original `reply_to` and keeps the thread.
3. The router sees a message to `claude:local_…`, delivers it into that session with `SendMessage`, and records
   `delivered`. The session reads it as a `<cross-session-message>` and carries on.

### W2. Codex asks a particular Claude session

As W1 from step 3. Codex knows the address because an earlier message from that session carried it in `from` or
`reply_to`, or from the directory (`mail.py who`).

### W3. Codex writes to "claude" without a session

The router decides, in this order, and records the reason in its `routed` receipt:

1. **Thread continuity.** If the message replies to, or shares a thread with, a message a Claude session sent, it goes
   to that session (the latest Claude participant in the thread).
2. **A role.** `claude:orchestrator` goes to the registered orchestrator.
3. **Clear ownership.** If the content plainly concerns work one live session owns (its registered topics, branch,
   title or plan) and the message is an `ask` or `tell` about that work, it goes there.
4. **Otherwise, the orchestrator.** Anything ambiguous, any `request` for work nobody owns yet, and any question that
   needs Alastair.

### W4. The orchestrator takes on a request

1. It reads the message and decides who does the work: an existing session (`SendMessage`), a new session
   (`start_session`, with the message id in the brief), or a subagent.
2. It records `delegated` with the owner's address and sends the sender a `tell` in the same thread: who owns the work
   now and their address, so further messages go straight there.
3. The owner replies in the thread when the work is done, from its own address.
4. A question in the message that only Alastair can answer is collated and asked by the orchestrator, as its rulings
   say; his answer goes back as a `reply` quoting his words.

### W5. Delivery fails

If `SendMessage` reports that the session is gone or refused the message, the router records `failed`, sends the
message on to the orchestrator with a note, and tells the sender in the thread that the original session is no longer
reachable. If no orchestrator is registered, the router leaves the message in its queue and says so in its own
transcript, where Alastair sees it.

### W6. The router itself

Started once, in the main project, from a short brief: "Load the agent-mail-router skill and run it." It registers as
`claude:router`, then loops: start `mail.py watch --for claude --once` in the background; when it exits, route every
message in `mail.py pending --for claude`; start the watch again. Delivery is at least once: if the router stops between
delivering and recording, the message may arrive twice, so recipients ignore a message id they have already handled.

## Trust

Codex is Alastair's own agent, so its messages are a colleague's, not a stranger's, but they are not Alastair. A
message from Codex never grants permission the receiving session would not otherwise have, and never counts as a ruling.
A ruling Codex relays must quote his words, and the orchestrator records it in AGENTS.md as a relayed ruling, checking
with him first when it is surprising. A session never asks a peer to do something its own permissions blocked.

## Slices

1. **S1, the substrate and Claude's side (this branch).** `mail.py` with its tests, the two Claude skills
   (`agent-mail` for every session, `agent-mail-router` for the router), this plan, the runbook, the gitignore line and
   a pointer in AGENTS.md so Codex can find the protocol.
2. **S2, Codex's side.** Whatever Codex needs to read its inbox and be woken (a Codex skill, an automation or an
   app-server hook), designed in Alastair's conversation with Codex. It uses the same `mail.py` and the same folder.
3. **S3, the router running.** Start the router session in the main checkout once S1 has landed, and a first real round
   trip: a Claude session asks Codex a question and gets the answer back.
4. **S4, later if needed.** Archiving old threads, a small viewer page, and a lock so only one router runs.

## Open questions

1. **For the Codex side (S2):** how a Codex thread names itself (its address), whether Codex's sandbox may write to
   `.agent-mail/` in the main checkout or needs `AGENT_MAIL_DIR` pointed elsewhere, and how an idle Codex thread gets
   woken when mail arrives.
2. **For Alastair:** whether the router should send him a push notification when a message has waited for the
   orchestrator for a long time (default: no, the orchestrator's own transcript is enough).
