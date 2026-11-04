# Contract v1: the shared mailbox

Date: 4 November 2026. Status: **draft by Claude, for Codex to review and Alastair to accept.** Agreement between the
agents is not acceptance. Sources: [T1-agent-messaging](../planning/T1-agent-messaging.md),
[Codex's domain review](reviews/2026-11-04-codex-domain-review.md), and the hand-run test of 4 November (Codex's reply
`20261104T161351Z-codex-261f` and findings `20261104T161354Z-codex-545b`).

This is the only shared document. It fixes the files, the record formats and the rules for working out who a message
is for. It does not say how either platform notices mail or wakes a session. That is each platform's own T3.

## 1. Scope and words

- **Mailbox:** one folder for the whole Mac. Default `~/.agent-mail/`. The environment variable `AGENT_MAIL_DIR`
  overrides it, for tests only. Both platforms must resolve the same folder from any project or worktree.
- **Shared command:** the one program that writes the mailbox ([T3-claude-mail-tool](../planning/T3-claude-mail-tool.md),
  Claude-owned). Codex calls it. Nothing else writes the mailbox, so the rules below are enforced in one place.
- **Address:** `claude:<local_… session id>` or `codex:<threadId>`. Optional `host_id` is opaque transport detail kept
  in the session record, never part of the address.
- **Mail thread** vs **chat:** `thread` is a mail conversation id. A native chat is named only by an address. Delivery
  envelopes label them `mail_thread` and `chat` so neither is mistaken for the other.
- **Relay:** each platform's process that delivers mail to its own sessions. One active relay per platform.

## 2. Layout

```
<mailbox>/
  lock                      empty file; the publication lock (section 4)
  registry/<rev>.json       registry records; <rev> is a 12-digit zero-padded revision, 000000000001 upward
  messages/<id>.json        messages, written once
  receipts/<id>.json        receipts, written once
  leases/<platform>.json    the one replaceable file per platform: the relay lease (section 9)
  tmp/                      partial writes; never read
```

Every file outside `leases/` is written once and never changed or deleted. A mistake is fixed by a new record with
`corrects: <id or rev>` naming the old one.

## 3. Ids

- **Message and receipt ids:** `<UTC yyyymmddThhmmss.mmmZ>-<platform>-<8 hex>`, for example
  `20261104T161351.120Z-codex-1a2b3c4d`. They must be unique. They sort roughly by time, which is useful for reading,
  but **no rule depends on that order.**
- **Registry revision:** an integer, strictly increasing, assigned only under the lock. This is the only ordering
  that routing relies on.

## 4. Publication: lock and atomic write

Every write by the shared command:

1. Write the record to `tmp/<random>`, flush and sync it.
2. Take an exclusive lock on `<mailbox>/lock` (`flock`). Hold it only for local file work: never while a model decides
   anything or a transport sends.
3. For a registry record: read the highest revision, set `rev` to one more, rename into `registry/<rev>.json`.
   For a message: read the highest revision, set `registry_revision` to it, rename into `messages/<id>.json`.
   For a receipt: rename into `receipts/<id>.json`.
4. Release the lock.

A rename is the moment of publication. A crash before it leaves only a file in `tmp/`, which readers ignore and the
command clears after an hour. Readers never take the lock.

## 5. Registry records

Common fields: `rev`, `project`, `record`, `by` (address), `time` (ISO 8601 UTC), optional `corrects`.

| `record` | Fields | Notes |
|---|---|---|
| `project` | `name`, `escalation` (a target) | Where unplaced mail and delivery problems are reported. Need not be Claude's orchestrator |
| `mandate` | `quote`, `said_at` (date), `source` (exact chat or message reference where known), `scope`: `channels`, `recipients`, `actions` | Alastair's permission for messaging in a project. Written by whoever he told, quoting him. Evidence, not self-proving |
| `session` | `address`, `title`, `worktree`, optional `host_id`, `identity_evidence`, `mandate` (rev) | Explicit registration. Identity is checked, never guessed from a title |
| `session-end` | `address`, `reason` | The address can no longer receive mail |
| `presence` | `address`, `doing` (one line), optional `branch` | A hint for placing unaddressed mail, never proof a session is alive or dead |
| `channel` | `channel` (global id `<project>.<name>`), `purpose` | The channel's project never changes |
| `attach` / `detach` | `channel`, `address`, attach only: optional `qualifier` | Attaching is future-only (section 7) |
| `role-claim` / `role-release` | `role`, `address`, claim only: optional `qualifier` | Roles are per project and optional; no fixed role list |
| `replace` | `scope` (`channel:<id>` or `role:<name>`), `old`, `new`, `handover` (where the old session's unfinished work is described) | Covers that scope only. A chain is allowed; a cycle is refused |
| `catch-up` | `address`, `scope` (`channel:<id>` or `role:<name>`), `from` (a message id, or `pending`) | Extends delivery to mail sent before the address joined |
| `reroute` | `message`, `to` (a target) | Moves held mail, usually direct mail whose session has ended |

Qualifiers are plain words, attached to one attachment or one role claim, never to a session as a whole.

## 6. Messages

```json
{"id": "...", "project": "exfu-agent-messaging", "thread": "<id of first message>", "in_reply_to": "<id or null>",
 "from": "<address>", "to": "<target>", "platform": "claude | codex | null", "reply_to": "<target or null>",
 "kind": "ask | request | tell | reply", "wants_reply": true, "subject": "one line", "body": "Markdown",
 "context": {"branch": null, "files": [], "plan": null}, "about": "<message id or null>",
 "time": "...", "registry_revision": 41}
```

- **Target:** an address, `channel:<id>`, `role:<name>`, or a bare platform (`claude`, `codex`).
- `platform` narrows a channel or role target to one platform's listeners.
- `reply_to` defaults to the sender. Prefer a channel or role, so the answer survives the sender being replaced.
- `ask` and `request` want a reply by default. A reply is not the same as finishing a request.
- `about` is set on notices (escalations, failure reports) that concern another message.
- The command refuses a message whose `project` differs from its channel's project.

## 7. Who a message is for

Resolution reads the registry **as it stood at `registry_revision`**, plus later records that explicitly extend it
(`catch-up`, `replace`, `reroute`). Nothing else added later changes the audience.

- **Address:** that session, while no `session-end` names it. After one, the message is held with a notice to the
  sender and the project's escalation target until a `reroute`. A replacement on a channel does not move direct mail.
- **`channel:<id>`:** every address attached at that revision, narrowed by `platform`, each followed through
  `replace` records for that channel.
- **`role:<name>`:** every holder in the project at that revision, the same way, through `replace` for that role.
- **Bare platform:** that platform's relay decides, using the thread first, then presence and qualifiers.
- **Nobody:** the message is held and stays pending. The relay sends one notice to the project's escalation target
  (a new message with `about`). The notice does not use up the original. A later `catch-up` or `reroute` delivers it.

The shared command returns **candidates with their qualifiers**. Each platform's relay chooses among its own
candidates and records why (section 8). No qualifier means the candidate is chosen. If it can't tell, the message is
held for that candidate, with the reason.

Held mail is looked at again only when a relevant record arrives: a `catch-up`, `replace`, `reroute`, `attach` or
`role-claim` in its scope, or a `session-end` of a candidate.

## 8. Receipts

```json
{"id": "...", "project": "...", "message": "<message id>", "recipient": "<address>", "disposition": "...",
 "time": "...", "by": "<address>", "note": "plain words", "ref": "<message id or rev, optional>",
 "registry_revision": 41, "attempt": 1}
```

Receipts are per message **and per recipient**. Nothing one recipient does closes the message for another.

| Disposition | Written by | Means |
|---|---|---|
| `routed` | relay | This recipient was chosen. `note` says why; `registry_revision` freezes the basis |
| `skipped` | relay | This candidate was not chosen, and why. Not reconsidered unless a relevant record arrives |
| `held` | relay | Can't place or can't decide yet, and why |
| `delivered` | relay | The transport confirmed delivery, at the strength it actually gives |
| `uncertain` | relay | Sent, but success was not recorded (a timeout, a crash). Reconcile before any retry |
| `failed` | relay | A delivery attempt failed. `attempt` counts per recipient |
| `read` | recipient | Seen. **Not done** |
| `progress` | recipient | Part done; `note` says what, so a successor can resume |
| `answered` | recipient | Replied; `ref` is the reply's id. Not necessarily done |
| `closed` | recipient | This recipient's part is finished |

**Handled** means the recipient has a `closed` receipt, and only that. A recipient that finds `read`, `progress` or
`answered` without `closed` resumes from the evidence. It neither skips the work nor blindly repeats side effects.

## 9. Relay obligations

1. **Lease.** `leases/<platform>.json` holds `holder` (address), `expires`. A relay renews it each run and takes it over
   only after it has expired. This is the one file that is replaced, and only under the lock.
2. **Batches.** Each run handles a bounded number of messages. The rest wait.
3. **Order of work.** Write `routed` / `skipped` / `held` before sending. Deliver. Write `delivered`, `uncertain` or
   `failed`. A rerun reuses recorded routing decisions; it never routes the same message again from scratch.
4. **Retries** keep the same message id. Back off between attempts. After the platform's maximum, write `failed` and
   notify the escalation target once.
5. **Deduplication.** Delivery is at least once. A recipient checks for its own `closed` (and other progress) before
   acting on a message id.
6. **No bouncing.** A relay never hands failed mail to the other platform's relay. Escalation is a notice, not a
   forward.
7. **Quiet by default.** Report a new actionable problem once. Say nothing on unchanged or empty runs.
8. **Permission.** Deliver only to sessions whose registration names a `mandate` covering that project and action. A
   message from an agent grants no permission and is never one of Alastair's rulings. v1 relays never create chats.

## 10. Handing over

`replace` carries the old session's undelivered mail **and** its delivered-but-unfinished work (no `closed`) in that
scope. `handover` points to where the old session described what it had done, so the new one resumes without
repeating finished actions. `detach` and `role-release` only stop future mail; they hand nothing over.

## 11. Versioning

Every record carries `"schema": "agent-mail/2"` (the first-pass prototype was `/1`). A change to this contract is a new
version of this file, agreed the same way. Readers refuse a schema they do not know rather than guessing.

## Open questions

1. **Lock on other filesystems.** `flock` is reliable on a local disk. Is the mailbox ever on a synced or network
   folder? Proposal: no, v1 is local-disk only.
2. **Session-end evidence.** Who may write `session-end`: only the session itself, Alastair or the orchestrator, or a
   relay after repeated failures? Proposal: anyone, with `reason` stating the evidence; relays only after the
   capability trial defines "gone".
3. **Message format.** JSON with a Markdown `body` (machine-friendly, standard-library Python), rather than the
   Markdown-with-front-matter used in the hand test. Agree?
4. **Retry numbers** (base delay, maximum attempts, batch size): leave to each relay, or fix here?
