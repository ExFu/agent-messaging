---
id: T1-agent-messaging
plan_kind: thematic
tier: 1
status: draft
---

# T1: agent messaging between Claude and Codex

Date: 3 November 2026. Status: **draft, Claude's proposal for the domain model and workflows**, to agree with Codex
before anything is built. Codex designs and builds Codex's side; this plan says what the shared part could be and how
Claude's side would use it. Nothing here is accepted until Alastair accepts it.

First drafted in the defry repository (`exfu-mobile-actuator`, branch `claude/claude-codex-messaging-cd7d98`) and moved
here on Alastair's word: "I've created a new project for this work, as it's likely to be useful in many projects, and
have skills, plugins etc as outputs." A sketch of the tool and the Claude skills from that first pass is parked in
[prototype/](../prototype/README.md). It is not an implementation and is not agreed.

## Why

Alastair, 3 November 2026: "I want to create a skill(s) that lets you and Codex chat with each other. I imagine some
shared messaging substrate in the project that both Claude and Codex have read-write access to." On Claude's side: "start
a session in the current project that watches for messages incoming from Codex, and sends them to the relevant Claude
session. Sessions asking for a response should therefore provide a session id so that this observer session can route
appropriately. If Codex messages without a target session Id, then the observer needs to work out which session to send
it to based on the content. I typically run a main orchestrator session as well in Claude. If in doubt, or if the
message asks for some particular piece of work that is as-yet unorchestrated, then it's the orchestrators job to plan
and run that work by farming to appropriate sub-session, sub-agents, and creating new ones if necessary."

Then, after talking with Codex: "we probably want stable channelIds. Both sides can register a new channelId as
necessary, and attach observers to that channelId. Each registration should optionally have some natural language
qualifiers that let other agents know why that registration exists. This allows me to change which agent session is
handling a particular message channel (e.g. if context window dies and I need to replace the session), and have
multiple agents listening to the same channel but handling different domains of interest from it (e.g. one channel
might be about updates to a blocking piece of work that multiple agents are waiting on to do their bit.) The observer
agent can then use this info to help guide routing if and as necessary. It may often be unnecessary, as each agent
itself should in principle know which messages and message content it cares about. So, a simple approach with
flexibility feels like the best win here." And: "I think the substrate should probably be global on this machine.
Channels should perhaps therefore also say which project they relate to." And: "roles are also a very good idea, so
that the sender can point the message while not knowing anything about the receiver sessions."

Today Claude and Codex meet only through files and handovers, and Alastair carries questions between them by hand.

## Principles

1. **Simple, with room to flex.** The substrate stores and delivers messages. Agents decide what matters to them.
   Natural-language qualifiers guide routing when they help; they are never a rules engine.
2. **One substrate for the whole Mac.** Every project uses it; messages, channels and roles each say which project
   they belong to.
3. **Stable names, replaceable sessions.** Senders write to a channel or a role, not to a session that may die. Who
   listens or holds a role can change without the sender knowing.
4. **Nothing is changed in place.** Messages are written once; what happens to them, and every change to channels and
   roles, is a new record. History is always readable, and two agents writing at once cannot clobber each other.
5. **Each platform delivers to its own sessions.** The substrate is shared; waking a session is platform work. Claude's
   observer delivers to Claude sessions. Codex's side is Codex's to design.
6. **A colleague, not the boss.** A message from another agent grants no permission and is never one of Alastair's
   rulings. Anything that needs him goes through Claude's orchestrator, as his ruling of 31 October says.

## Domain model (proposal)

| Thing | What it is |
|---|---|
| **Project** | A short stable name (`defry`, `exfu-agent-messaging`). Scopes roles and labels channels and messages. |
| **Session address** | `<platform>:<session id>`, platform `claude` or `codex`. A Claude desktop session's id is in `$CLAUDE_CODE_HOST_SESSION_ID`, so a session never has to be told who it is. How a Codex session names itself is Codex's call. |
| **Channel** | A stable id (`defry.invite-codes`), its project, and a purpose: why it exists, in natural language. Anyone may create one. |
| **Attachment** | A session listening to a channel, with optional qualifiers: what it handles from that channel ("the unlock screen and its copy"). Many per channel, from either platform. |
| **Role** | A named job within a project (`orchestrator`, `design`, `backend`), held by one or more sessions, each with optional qualifiers. Lets a sender point a message at a job without knowing who does it. |
| **Replacement** | An attachment or role claim that says which session it takes over from. Mail the old session never received goes to the new one. |
| **Presence** | A session saying it is around: title, project, branch, and a line of what it is doing. Used only for placing mail that names no channel, role or session. |
| **Target** | Where a message goes: a session address, `role:<name>`, `channel:<id>`, or a bare platform (`claude`, `codex`: that platform works out who). |
| **Message** | Written once: id (sorts by time), project, thread, in-reply-to, from, to (a target), reply-to (a target; defaults to the sender), kind, wants-reply, subject, body (Markdown), context (branch, files, plan), time. |
| **Kind** | `ask` (a question), `request` (a piece of work), `tell` (a notice), `reply` (an answer). Ask and request want a reply by default. |
| **Thread** | Every message in a conversation carries the id of the message that opened it. |
| **Receipt** | One event about one message, naming the session it concerns where that matters: routed, held, delivered, failed, read, answered, delegated, closed. |
| **Observer** | A platform's process for noticing mail for its sessions and delivering it. Claude's is one long-lived router session. |

### Resolving a message

- **A session address:** that session.
- **`channel:<id>`:** every session attached when the message was sent (attaching later does not replay old mail), each
  followed through any replacement since. Each platform's observer delivers to its own platform's listeners.
- **`role:<name>`:** every holder of that role in the message's project, the same way.
- **Nobody listening, or nobody holding the role:** the project's `orchestrator` role, as the fallback. If nobody holds
  that either, the message is unplaced and waits ("held") until someone does.
- **A bare platform:** that platform's observer decides. Claude's looks first at the thread (a reply goes back to the
  session that asked), then at presence and qualifiers, and otherwise gives it to the orchestrator.

Delivery is at least once, so a session ignores a message id it has already handled.

## Workflows (proposal)

1. **Ask a question across platforms.** A session sends an `ask` to a role, a channel or a session, with reply-to set
   to itself (or to a channel, so the answer survives the session being replaced). The answer is a `reply` in the same
   thread, delivered by the asker's platform's observer.
2. **A shared blocker.** One channel per blocking piece of work. Everyone waiting attaches, with qualifiers saying what
   they need from it. The owner posts `tell`s; each listener decides what concerns it.
3. **Replacing a session.** When a session's context runs out, Alastair or the orchestrator attaches the new session to
   its channels and gives it its roles, each marked as replacing the old one. Undelivered mail follows.
4. **Unowned work.** A `request` to a role nobody holds, or to the orchestrator, reaches Claude's orchestrator. It plans
   the work, hands it to an existing session, a new session or a subagent, records who owns it, and tells the sender, so
   further messages go straight to the owner.
5. **Delivery fails.** If the target session is gone, the observer records the failure, gives the message to the
   orchestrator instead, and tells the sender in the thread.
6. **A question for Alastair.** It goes to the orchestrator, which collates questions for him and replies quoting his
   words.

## Who builds what

Every piece of work has exactly one owner, and every T3 belongs to exactly one platform. The only shared document is
the contract: the file layout, the message, receipt and registry formats, and the target rules. Both sides agree it
and either may propose a new version. [T2-messaging-v1](T2-messaging-v1.md) lists every piece and its owner.

| Piece | Owner | Plan |
|---|---|---|
| The contract (formats and rules) | Claude and Codex, jointly; Alastair accepts it | `docs/contract-v1.md`, written once this T1 is agreed |
| The shared command for the files | Claude (proposed; see question 2 below) | [T3-claude-mail-tool](T3-claude-mail-tool.md) |
| Claude's router session | Claude | [T3-claude-router](T3-claude-router.md) |
| Skills for Claude sessions and the orchestrator, packaged as a plugin | Claude | [T3-claude-session-skills](T3-claude-session-skills.md) |
| How Codex sessions name themselves, notice mail and get it delivered | Codex | Codex's own T3s |

Claude builds nothing on Codex's side and makes no assumptions about how it works. Codex's side only has to meet the
contract.

## Claude's side (proposal)

Detailed in Claude's three T3s above. In short:

- **The router session.** Started once per Mac from a short brief, on a cheap model. It waits on a background command
  that exits when mail for Claude is waiting (no polling in its context), then for each message: resolves the targets,
  checks each session is alive, delivers with `SendMessage` to the session's `local_…` id, and records what it did. It
  never answers a message or does its work. Delivered text opens with one self-contained line, says why the session gets
  it ("you are attached to channel:defry.invite-codes (your note: the unlock screen)") and ends with how to reply.
- **Every Claude session** says hello when it starts talking to other agents, attaches to the channels it cares about,
  sends, reads and replies through the shared tool, and never waits or polls for an answer: the router brings it.
- **The orchestrator** holds the `orchestrator` role for its project and owns everything unplaced or unowned.
- **Skills:** one for every session (send, receive, reply, channels, roles, trust), one for the router. Where they live
  (a plugin from this project, most likely) is part of the build plan, after agreement.

A dry run of the first sketch (a subagent following the router skill against a test mailbox) placed four messages
correctly and found ten unclear points, all fixed in the sketch. The lessons that shape the design: check a session is
alive before delivering; a failed delivery stays queued until it reaches someone; a message the router cannot place yet
must be marked so the watcher does not wake for it again and again; a message wanting no reply must not end by asking
for one.

## For agreement with Codex

1. Is this domain model viable from Codex's side: channels, attachments with qualifiers, roles per project,
   replacements, presence, and the four kinds of target?
2. Does the shared part stay as plain files under `~/.agent-mail/` and one small shared command both sides call, or
   does Codex need something else (a different place, a service, a different format)? The format is versioned, so
   either side can propose changes. If it is one command, Claude proposes to own it (T3-claude-mail-tool), and Codex
   calls it or writes its own client against the contract, whichever suits Codex.
3. How a Codex session names itself, and how Codex's side notices and delivers mail. Codex's to decide; Claude's side
   only needs the address format and the receipts to be shared.
4. Are channel ids global (`defry.invite-codes`) with the project as a label, as proposed, or scoped per project like
   roles?
5. Should a channel or role ever be closed or expire, or is detaching enough?

## For Alastair

1. Accept this T1 (as amended after the Codex conversation), and then a build plan.
2. Where the tool and skills ship: a plugin from this project, installed in every project that wants it (proposed).


## Codex review proposal, 4 November 2026

Codex considers the domain viable, subject to the requested changes in
[the domain review](../docs/reviews/2026-11-04-codex-domain-review.md). These are proposals, not accepted rulings.
The review supplies Codex's answers to the five agreement questions above. Claude retains the shared command;
Codex consumes it and supplies one scheduled global relay plus session skills. The contract must resolve catch-up
for late subscribers, qualifier-based selection, per-recipient receipts, unfinished-work handover, scoped replacement,
platform selection and configurable project escalation before either side builds against it.

Alastair's Codex-chat direction: the registry has a channel-to-session map and optional natural-language qualifiers.
He explicitly said: "I don't think we need 'owner' concepts per se, given we can use natural language directives for
more sophisticated and unforseeable routing variations." T3 implementation ownership remains single-platform;
message handling needs no fixed owner schema. New Codex chats are manually created and registered for v1.
