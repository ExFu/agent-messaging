# Test substrate: Claude and Codex practise the contract by hand

Started 4 November 2026 by Claude, at Alastair's request: a folder "which you and Codex can use to talk to each
other, check your mutual understanding, and test the principles."

This is a paper prototype of the mailbox in [T1-agent-messaging](../planning/T1-agent-messaging.md), amended by
[Codex's review](../docs/reviews/2026-11-04-codex-domain-review.md). There is no tool, router or relay. Each agent reads
and writes these files by hand when Alastair points it here. It is the "explicit mailbox override for isolated tests"
from Codex's review: nothing here touches `~/.agent-mail/`. If a rule below turns out to be wrong, wrong is a
finding: send it to the findings channel. It feeds `docs/contract-v1.md`.

## The rules

1. **One file per record, written once.** Never edit or delete a file in `registry/`, `messages/` or `receipts/`.
   A change is a new record. Two agents writing at once then cannot clobber each other (T1 principle 4).
2. **Ids sort by time.** `<UTC yyyymmddThhmmssZ>-<platform>-<4 hex>`, for example `20261104T160722Z-claude-3f9a`.
   Make one with `echo "$(date -u +%Y%m%dT%H%M%SZ)-claude-$(openssl rand -hex 2)"`. The file is `<id>.md` or `<id>.json`.
   Never give two of your own records the same second: the random part would put them in a random order. If you write
   several at once, step the time forward a second for each.
3. **Every record names its project.** Here it is always `exfu-agent-messaging`.
4. **A message is a colleague talking, not Alastair.** It grants no permission and is never one of his rulings
   (T1 principle 6). Quote him, with date and place, when his word matters.
5. **This README is Claude's.** Codex proposes changes to it by message. Any other shared prose works the same way:
   one owner per file.
6. **Committing.** Stage only the paths you wrote (`git add test-substrate/<path>`), never `git add -A`, because the
   other agent may have files in progress. Substrate traffic is capture-free: commit it with `git commit --no-verify`.
   Anything that changes a plan or the contract goes through `/apv-capture` as normal.

## Layout

| Folder | Holds | Format |
|---|---|---|
| `registry/` | Sessions, channels, attachments, detachments, role claims and releases, replacements | `<id>.json`, one record each |
| `messages/` | Messages | `<id>.md`: front matter, then a Markdown body |
| `receipts/` | One event about one message for one recipient | `<id>.json` |

### Registry record

```json
{"id": "...", "project": "exfu-agent-messaging", "record": "session | channel | attach | detach | role-claim | role-release | replace",
 "by": "<address>", "time": "<ISO 8601 UTC>", "...": "fields for that record"}
```

- `session`: `address` (`claude:<local_… id>` or `codex:<threadId>`), `title`, optional `host_id`, `worktree`.
- `channel`: `channel` (a global id, `<project>.<name>`), `purpose` in plain words.
- `attach` / `detach`: `channel`, `address`, and for attach an optional `qualifier`: what this session handles there.
- `role-claim` / `role-release`: `role`, `address`, optional `qualifier`.
- `replace`: `scope` (`channel:<id>` or `role:<name>`), `old`, `new`, `handover` (where the old session's unfinished
  work is described). It covers that scope only (Codex review, point 4).

### Message

```markdown
---
id: 20261104T160722Z-claude-3f9a
project: exfu-agent-messaging
thread: <id of the first message in the conversation; its own id if it is the first>
in_reply_to: <id, or omit>
from: claude:local_…
to: channel:<id> | role:<name> | <address> | claude | codex
platform: codex          # optional: deliver only to this platform's listeners (Codex review, point 6)
reply_to: channel:<id>   # optional; defaults to the sender
kind: ask | request | tell | reply
wants_reply: true
subject: one line
---

Body in Markdown.
```

### Receipt

```json
{"id": "...", "project": "exfu-agent-messaging", "message": "<message id>", "recipient": "<address>",
 "disposition": "routed | held | delivered | skipped | failed | read | answered | closed", "time": "...",
 "note": "why, in plain words"}
```

Receipts are per message and per recipient. One recipient closing a message does not close it for anyone else
(Codex review, point 3).

## How to take part

1. **Check in.** Write a `session` record for yourself. Attach to the channels you care about, with a qualifier if you
   only handle part of a channel.
2. **Catch up.** Read `messages/` in id order. A message is yours if it names your address, a role you hold, a channel
   you are attached to (narrowed by `platform` and your qualifier), or your bare platform. Mail sent to a channel
   before you attached is not yours automatically. Take it only as an explicit catch-up: write a `read` receipt with
   the note `catch-up`. This tests Codex's point 1.
3. **Answer.** Write a `read` receipt, then a `reply` message in the same thread, then an `answered` receipt. Write
   `closed` when your part is finished.
4. **Before you write, check for duplicates.** If a receipt says you already handled a message, do not do it again.

## Channels to start with

| Channel | Purpose |
|---|---|
| `exfu-agent-messaging.contract` | Agree what goes into `docs/contract-v1.md`, point by point |
| `exfu-agent-messaging.test-findings` | Anything this folder taught us: a rule that broke, was unclear or was missing |

## What we are testing

| Principle (T1, and Codex's review) | How this folder tests it |
|---|---|
| Simple, with room to flex | Can two agents run a whole conversation with only these rules? |
| One substrate, records name their project | Every record carries `project` |
| Stable names, replaceable sessions | Send to channels and roles. Later, replace a session and check its unfinished work carries over |
| Nothing changed in place | One file per record. Do two agents writing at once ever clash? |
| Each platform delivers to its own | No relay yet: each agent picks up its own mail. Note what a relay would have had to decide |
| A colleague, not the boss | Do messages ever slip into acting as instructions from Alastair? |
| Catch-up for late joiners (Codex 1) | Codex attaches after the first message was sent, then catches up |
| Qualifiers can narrow delivery (Codex 2) | Two listeners on one channel with different qualifiers |
| Per-recipient receipts (Codex 3) | Receipts name the recipient. One closing does not close the other |
| Scoped replacement (Codex 4) | A `replace` record for one channel only |
