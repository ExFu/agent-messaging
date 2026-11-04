# Contract v1: the shared mailbox

Date: 4 November 2026. Status: **draft 3 by Claude, for Codex to review and Alastair to accept.** Agreement between
the agents is not acceptance. Sources: [T1-agent-messaging](../planning/T1-agent-messaging.md),
[Codex's domain review](reviews/2026-11-04-codex-domain-review.md), and the hand-run test of 4 November. Draft 2 takes
Codex's review of draft 1 (message `20261104T163452Z-codex-7600`): six amendments and four answers, all adopted.
Draft 3 takes Codex's review of draft 2 (message `20261104T164344Z-codex-7b2c`): trace corrections, explicit
publication recovery, handover authority, and small format fixes, all adopted.
Worked examples: [contract-v1-traces.md](contract-v1-traces.md).

This is the only shared document. It fixes the files, the record formats and the rules for working out who a message
is for. It does not say how either platform notices mail or wakes a session. That is each platform's own T3.

## 1. Scope and words

- **Mailbox:** one folder for the whole Mac, on a local disk (never a synced or network folder). Default
  `~/.agent-mail/`. The environment variable `AGENT_MAIL_DIR` overrides it, for tests only. Both platforms must
  resolve the same folder from any project or worktree.
- **Shared command:** the one program that writes the mailbox ([T3-claude-mail-tool](../planning/T3-claude-mail-tool.md),
  Claude-owned). Codex calls it. Nothing else writes the mailbox, so the rules below are enforced in one place.
- **Address:** `claude:<local_… session id>` or `codex:<threadId>`. Optional `host_id` is opaque transport detail kept
  in the session record, never part of the address.
- **Mail thread** vs **chat:** `thread` is a mail conversation id. A native chat is named only by an address. Delivery
  envelopes label them `mail_thread` and `chat` so neither is mistaken for the other.
- **Relay:** each platform's process that delivers mail to its own sessions. One active relay per platform.
- **Obligation:** one selected recipient's duty towards one message. It opens with a `routed` receipt and ends with
  that recipient's `closed`, or with `transferred` when a replacement moves it to a successor. It is the unit that is delivered, retried, resumed and handed over.

## 2. Layout

```
<mailbox>/
  lock                          empty file; the publication lock (section 4)
  seq                           the last sequence number issued (section 3)
  registry/<seq>-<id>.json      registry records
  messages/<seq>-<id>.json      messages
  receipts/<seq>-<id>.json      receipts
  leases/<platform>.json        the relay lease (section 9)
  tmp/                          writes in progress; never read
```

Every file in `registry/`, `messages/` and `receipts/` is published once and never changed or deleted. Only `seq` and
`leases/` are replaced, and only under the lock.

## 3. Ids and order

- **Id:** `<UTC yyyymmddThhmmss.mmmZ>-<platform>-<8 hex>`, unique across the mailbox. Records refer to each other by
  id. Ids are readable, but **no rule depends on their order.**
- **Sequence (`seq`):** one integer for the whole mailbox, assigned to every published record (registry, message and
  receipt) under the lock. Strictly increasing, no reuse. This is the only order any rule relies on. File names are
  zero-padded to 12 digits so a listing sorts by it.
- **Registry snapshot:** a message's audience is worked out from the registry records with `seq` lower than the
  message's own. The message also stores `registry_revision`, the `seq` of the newest such record, so readers need not
  recompute it.

## 4. Publication

**Readers and writers both lock.** The shared command takes Python `fcntl.flock` on `<mailbox>/lock`: **shared** for
every read, **exclusive** for every write and every recovery. Either lock is held only for local file work, never while
a model decides anything or a transport sends. Nobody reads the mailbox except through the command, so nobody can see a
half-published record.

**A write**, in this order:

1. Build the payload and check everything that needs no lock (schema, required fields, section 12).
2. Take the exclusive lock. Run recovery first if it is needed (below).
3. Check everything that needs the lock: the id is not already published, the channel's project matches, the lease is
   current for relay receipts (section 9), any `corrects` or `handover` is valid (sections 5 and 10).
4. Assign `seq` (last issued plus one) and, for a message, `registry_revision`.
5. Write the **final** content to `tmp/<seq>.tmp`, then flush and `fsync` it.
6. Publish with `os.link` into the destination, which fails rather than overwrite, then `fsync` the destination
   directory. Remove the temp file.
7. Write the new value to `tmp/seq.tmp`, `fsync` it, rename it over `seq`, and `fsync` the mailbox directory.
8. Release the lock.

A record is **published** when step 6's directory `fsync` returns. Several records may be published in one lock hold
(section 10 uses this). They are visible to readers only together, once the lock is released.

**A read** takes the shared lock and checks whether recovery is needed. If so, it releases the lock, takes the
exclusive lock, recovers, and starts again. Then it reads.

**Recovery is needed** when `tmp/` holds any file, or `seq` differs from the highest published `seq`. Under the
exclusive lock:
- **`tmp/<n>.tmp` with no published record `n`:** the writer died before step 6, so the record never existed. Delete
  the temp file.
- **`tmp/<n>.tmp` with a published record `n`:** the writer died after linking. The content is complete, because it
  was synced in step 5. Keep the record, `fsync` its directory, and delete the temp file.
- **`seq` behind the highest published `seq`:** set it to that value as in step 7.
- **`tmp/seq.tmp`:** delete it. Rebuild `seq` as above.

A writer that dies before step 6 published nothing. One that dies after step 6 published its record, and recovery
makes that durable. A whole-machine crash before step 6's `fsync` may lose the link, but no reader could have seen it,
because the exclusive lock was still held.

## 5. Registry records

Common fields: `schema`, `id`, `seq`, `project`, `record`, `by` (address), `time` (ISO 8601 UTC), optional `corrects`.

| `record` | Fields | Notes |
|---|---|---|
| `project` | `name`, `escalation` (a target) | Where unplaced mail and delivery problems are reported. Need not be Claude's orchestrator |
| `mandate` | `quote`, `said_at` (date), `source` (exact chat or message reference where known), `scope`: `channels`, `recipients`, `actions` | Alastair's permission for messaging in a project. Written by the agent he said it to, quoting the instruction it actually received. It lasts until revoked |
| `mandate-revoke` | `mandate` (id), `quote`, `said_at`, `source` | Withdraws that mandate from its own `seq` on, on the same evidence rule |
| `relay` | `platform`, `base_delay_s`, `max_backoff_s`, `max_attempts`, `lease_s`, `batch` | Each platform publishes its own numbers, chosen from its capability trial |
| `session` | `address`, `title`, `worktree`, optional `host_id`, `identity_evidence`, `mandate` (id) | Explicit registration. Identity is checked, never guessed from a title |
| `session-end` | `address`, `reason`, `evidence` | Scoped to its `project`. See section 7 for who may write it |
| `presence` | `address`, `doing` (one line), optional `branch` | A hint for placing unaddressed mail, never proof a session is alive or dead |
| `channel` | `channel` (global id `<project>.<name>`), `purpose` | The channel's project never changes |
| `attach` | `channel`, `address`, optional `qualifier`, optional `updates` (id of an earlier attach) | Future-only (section 7). `updates` changes the qualifier of that binding |
| `detach` | `channel`, `address` | Stops future mail. Hands nothing over |
| `role-claim` | `role`, `address`, optional `qualifier`, optional `updates` | Roles are per project and optional; no fixed role list |
| `role-release` | `role`, `address` | Like `detach` |
| `replace` | `scope` (`channel:<id>` or `role:<name>`), `old`, `new`, `handover` | Section 10. A chain is allowed; a cycle is refused |
| `catch-up` | `address`, `scope`, `from` (a message id, or `pending`) | Section 7 |
| `reroute` | `message`, `to` (a target) | Moves held mail |
| `retry` | `message`, `recipient` | Reopens an obligation that ran out of attempts |

**Corrections.** A record with `corrects: <id>` supersedes that record from its own `seq` onward. A snapshot taken
earlier keeps using the old record: a correction never rewrites a decision already made from it. The command refuses a
correction of a different record type, or by an address that could not have written the original.

Qualifiers are plain words on one attachment or one role claim, never on a session as a whole.

## 6. Messages

```json
{"schema": "agent-mail/2", "id": "20261104T163452.120Z-codex-1a2b3c4d", "seq": 57, "registry_revision": 52,
 "project": "exfu-agent-messaging", "thread": "<id of first message>", "in_reply_to": null,
 "by": "codex:01a1…", "from": "codex:01a1…", "to": "channel:exfu-agent-messaging.contract", "platform": "claude",
 "reply_to": "channel:exfu-agent-messaging.contract", "reply_platform": "codex",
 "kind": "ask", "wants_reply": true, "subject": "one line", "body": "Markdown",
 "context": {"branch": null, "files": [], "plan": null}, "about": null, "time": "2026-11-04T16:34:52.120Z"}
```

- **Target:** an address, `channel:<id>`, `role:<name>`, or a bare platform (`claude`, `codex`).
- `platform` narrows a channel or role target to one platform's listeners. Null means both.
- `reply_to` defaults to the sender. Prefer a channel or role, so the answer survives the sender being replaced.
- `reply_platform` says which platform's listeners a reply to a channel or role should reach. It defaults to the
  sender's own platform. `any` asks for a broadcast. It does nothing for a reply to an address.
- **A reply** copies the original's `reply_to` into its `to` and `reply_platform` into its `platform` (`any` becomes
  `null`), unless the replier deliberately overrides them. Its audience is worked out at the reply's own `seq`.
- `by` is the address that published the record. For a message it equals `from`.
- `ask` and `request` want a reply by default. A reply is not the same as finishing a request.
- `about` is set on notices (escalations, failure reports) that concern another message.
- The command refuses a message whose `project` differs from its channel's project.

## 7. Who a message is for, and whether it can be delivered now

Two separate questions.

**Audience: fixed when the message is sent.** Candidates come from the registry snapshot (section 3), plus records
that explicitly extend it: `catch-up`, `replace`, `reroute`, and `attach` or `role-claim` with `updates`. Nothing else
added later changes who the message was for.

- **Address:** that session.
- **`channel:<id>`:** every address attached in the snapshot, narrowed by `platform`, each followed through `replace`
  records for that channel.
- **`role:<name>`:** every holder in the project in the snapshot, the same way through `replace` for that role.
- **Bare platform:** that platform's relay decides, using the thread first, then presence and qualifiers.
- **Nobody:** the relay writes a `held` receipt with `recipient: null` and the message's scope, and sends one notice
  to the project's escalation target (a new message with `about`). The notice does not use up the original.

The shared command returns **candidates with their qualifiers**. Each platform's relay chooses among its own
candidates and records each choice (section 8). No qualifier means chosen. If it can't tell, it holds that candidate,
with the reason.

**Deliverability: read from the current registry, every time.** A `session-end`, a `mandate-revoke` or a transport
problem after the message can block delivery to a chosen recipient. It never rewrites the audience. The obligation is
held, with the reason. What releases it depends on the reason:
- **Ended session:** a `reroute` or a `replace`. Direct mail to an ended address is held with a notice to the sender
  and the escalation target. A replacement on a channel does not move direct mail.
- **No permission:** a new `mandate` covering it.
- **Transient transport problem:** time. The `held` receipt sets `next_attempt_at`, and the relay tries again then.

**Replaced before routing.** If a `replace` arrives before the relay has routed a message, the relay first decides on
the original candidate, using that binding's qualifier from the snapshot. If chosen, the obligation goes to the
successor (section 10). If not, it is skipped as usual. Not yet routed because no relay has run is not the same as
skipped: the mail is never lost. A candidate already skipped stays skipped unless something explicitly reconsiders it.

**Who may write `session-end`:** the session itself; Alastair (through an agent quoting him, with `evidence`); or a
project orchestrator within a mandate he recorded. A relay may write one only on an authoritative permanent-retirement
signal that its capability trial has established. Timeouts, a missing list entry, an archived state or a permission
error are not enough on their own: hold with the observed reason instead. It is scoped to its `project`, because one
chat may be registered in several.

**Changing a qualifier.** A new `attach` or `role-claim` with `updates` replaces that binding's qualifier from its
`seq` on. Held and skipped decisions for that binding are re-examined. The new decision is a new receipt carrying the
newer `registry_revision`. Old `routed` receipts stand.

**Catch-up.** A `catch-up` record covers messages in its scope with `seq` from `from` (inclusive: the `seq` of that
message) up to the catch-up record's own `seq` (inclusive bound fixed at creation). `from: pending` instead covers
every message in scope below that bound with an unfinished obligation, or with an unresolved `recipient: null` hold.
To avoid a gap, attach first, then catch up. Attachment covers everything after it, and catch-up everything before,
with overlap removed per recipient.

**Re-examining held mail** happens only when a relevant record arrives in its scope (`catch-up`, `replace`, `reroute`,
`attach`, `role-claim`, `session-end`, `mandate`, `mandate-revoke` or `retry`), or when a held receipt's
`next_attempt_at` passes.

## 8. Receipts

```json
{"schema": "agent-mail/2", "id": "...", "seq": 61, "project": "...", "message": "<message id>",
 "recipient": "<address, or null for a whole-message hold>", "scope": "<channel:… or role:…; required when recipient is null>",
 "via": "<channel:… | role:… | address>", "disposition": "...", "by": "<address>", "time": "...",
 "note": "plain words", "ref": null, "registry_revision": 52,
 "attempt_id": null, "attempt": null, "next_attempt_at": null, "lease_generation": null,
 "handover": null}
```

Receipts are per message **and per recipient**, ordered by `seq`. Nothing one recipient does closes the message for
another. `via` records which channel, role or direct address the obligation came through, for handover (section 10).

| Disposition | Written by | Means |
|---|---|---|
| `routed` | relay | This recipient was chosen. `note` says why; `registry_revision` freezes the basis. Opens an obligation |
| `skipped` | relay | This candidate was not chosen, and why. No obligation |
| `held` | relay | Can't place, decide or deliver yet, and why |
| `attempt-started` | relay | About to call the transport. New `attempt_id`, `attempt` number. Written **before** sending |
| `delivered` | relay | The transport confirmed delivery, at the strength it actually gives. Names its `attempt_id` |
| `failed` | relay | That attempt failed. Names its `attempt_id`; sets `next_attempt_at` |
| `uncertain` | relay | That attempt's outcome is unknown. Names its `attempt_id`. Reconcile before any retry |
| `exhausted` | relay | Out of attempts. The obligation is held; one notice goes to the escalation target |
| `transferred` | relay | A `replace` moved this obligation to a successor (section 10). Ends it without claiming it was finished. **Stop acting on it** |
| `read` | recipient | Seen. **Not done** |
| `progress` | recipient | Part done; `note` says what, so a successor can resume |
| `answered` | recipient | Replied; `ref` is the reply's id. Not necessarily done |
| `closed` | recipient | This recipient's part is finished. Closes the obligation |

**Handled** means the recipient has `closed`, and only that. Before acting, a recipient checks its own receipts and
the registry:
- `closed`: leave it, it's finished.
- `transferred`, or a `replace` of the scope it came through: stop. It is no longer yours.
- Otherwise, `read`, `progress` or `answered` means resume from the evidence. Don't skip the work, and don't repeat
  anything already done. A `closed` check cannot stop two simultaneous invocations both acting.
Each platform must therefore give a session one message at a time, by queueing in the transport or by the session
handling its mail one item at a time. The capability trial shows which.

## 9. Relay obligations

1. **Lease.** `leases/<platform>.json` holds `holder`, `generation` (an opaque token, new on every takeover) and
   `expires`. A relay takes it over only after it has expired. Every relay receipt carries `lease_generation`, and the
   command refuses it unless that generation is current and unexpired. A relay renews before each send. A relay whose
   lease has lapsed stops at once. A lease cannot recall a send already in flight, so delivery stays at least once.
2. **Batches.** Each run handles at most the relay's published `batch` of obligations. The rest wait.
3. **Order of work for one obligation:** `routed` (or `skipped` / `held`) → `attempt-started` → transport →
   `delivered`, `failed` or `uncertain`. A rerun reuses recorded routing decisions. It never routes a message again
   from scratch.
4. **Recovery.** An `attempt-started` with no outcome means the relay died mid-send. Its successor writes `uncertain`
   for it, then reconciles using the message id and whatever evidence the transport gives, before any retry.
5. **Retries** keep the message id, start a new `attempt_id`, and honour `next_attempt_at`, so the budget persists
   across runs. `uncertain` is reconciled, not counted as a failure by default. After `max_attempts` the relay writes
   `exhausted`. Only a `retry` record reopens it.
6. **Deduplication.** Delivery is at least once, never promised exactly once. Recipients deduplicate by message id
   before side effects (section 8).
7. **No bouncing.** A relay never hands failed mail to the other platform's relay. Escalation is a notice, not a
   forward.
8. **Quiet by default.** Report a new actionable problem once. Say nothing on unchanged or empty runs.
9. **Permission.** Deliver only to sessions whose registration names a `mandate` covering that project and action. A
   message from an agent grants no permission and is never one of Alastair's rulings. v1 relays never create chats.

## 10. Handing over

**When to replace.** A registry record can't recall work already running. Write `replace` only when the old session
has stopped (its context is gone), or has reached a handover point and said so in its `handover` description.

**What transfers.** The old session's **open obligations that came through that scope** (`via` matches): those with
`routed` and neither `closed` nor `transferred`. That covers both undelivered mail and delivered-but-unfinished work.
Skipped candidates had no obligation and transfer nothing. Obligations through other channels, roles or direct mail
stay with the old session.

**When it takes effect.** At the `replace` record's own `seq`. From then on, the old session must not start, resume or
send anything for those obligations, and its relay must not deliver them to it. This holds even before any receipts are
written. The receipts that follow only record the move.

**Recording it.** Each transfer has a stable identity: `handover: {"replace": <replace id>, "source": <the old
routed receipt's id>}`. The relay writes both receipts **in one exclusive-lock hold** (section 4):
1. a `routed` for the successor, `via` the same scope, carrying `handover`;
2. a `transferred` for the old session, carrying the same `handover`.

The command refuses a second `routed` or `transferred` with a `handover` already used, so repeating the step is
harmless. If a crash leaves one without the other, recovery writes the missing one. It never opens a second successor.

**Racing a close.** The lock puts every `closed` and every transfer in order. If the old session's `closed` comes first,
the work is finished and is not reopened or transferred. Once `transferred` exists, the command refuses a `closed`
from the old session for that obligation.

The old session's `progress` receipts and the `handover` description travel with the obligation, so the successor
resumes rather than restarts. `detach` and `role-release` only stop future mail; they hand nothing over.

## 11. Versioning

Every record carries `"schema": "agent-mail/2"` (the first-pass prototype was `/1`). A change to this contract is a new
version of this file, agreed the same way. Readers refuse a schema they do not know rather than guessing.

## 12. Required fields

| Record | Always required | Required when |
|---|---|---|
| Any | `schema`, `id`, `seq`, `project`, `by`, `time` | |
| Registry | `record` plus that record's fields in section 5 | `corrects` names a published record of the same type |
| Message | `thread`, `from`, `to`, `kind`, `wants_reply`, `subject`, `body`, `registry_revision` | `in_reply_to` when `kind` is `reply`; `about` on notices |
| Receipt | `message`, `disposition`, `registry_revision` | `recipient` or (`recipient: null` and `scope`); `via` on `routed`; `attempt_id` on attempt outcomes; `ref` on `answered`; `lease_generation` on relay receipts; `handover` on `transferred` and on a successor's `routed` |

Unknown fields are kept and ignored, so either side can add one without breaking the other.

## Settled from draft 1

- Local disk only, with `fcntl.flock` from Python.
- `session-end`: the session, Alastair, or an orchestrator under his mandate; a relay only on a trial-proven signal;
  scoped to a project.
- JSON with a Markdown `body`. The hand test's Markdown files stay a paper convention.
- Retry numbers belong to each platform (the `relay` record). The rules for them are common.

## Settled from draft 2

- **Writing for Alastair.** An agent may record a `mandate`, `mandate-revoke` or `session-end` only as a faithful
  record of an instruction it received directly from him, within that instruction's scope, with the exact source
  where available. Another agent's say-so, or a quote copied from elsewhere, is not authority. A mandate persists, so
  ordinary authorised delivery never turns into repeated permission prompts.
- **Long transport calls.** Correctness never rests on the lease being long enough. Each relay uses a finite transport
  timeout and a lease with measured headroom, and renews before each send. A slow or suspended process can still
  outlive both. So once the lease has lapsed or been taken over, a late completion is reconciled as `uncertain` under
  the current generation: a stale writer cannot finalise receipts. If a platform's transport call cannot be bounded
  or cancelled, its T3 says so and relies on that `uncertain` recovery. Ten times the slowest send is a starting
  number for tuning, not a guarantee.

## Open questions

None at draft 3. Scheduling cadence, transport behaviour and the "session gone" signal are left to Codex's capability
trial, as agreed.
