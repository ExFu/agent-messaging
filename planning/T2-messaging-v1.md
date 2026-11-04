---
id: T2-messaging-v1
plan_kind: thematic
tier: 2
status: completed
---

# T2: messaging v1, the first working round trip

Date: 3 November 2026. Parent: [T1-agent-messaging](T1-agent-messaging.md). Status: **draft**, waiting on the T1 being
agreed with Codex and accepted by Alastair. Nothing in it is built until then.

## What v1 is

A Claude session and a Codex session can each send the other a question through a role or a channel, and get the
answer back, with neither knowing the other's session id in advance. A message nobody can take reaches Claude's
orchestrator. A replaced session picks up the mail its predecessor missed.

## Pieces and owners

Each piece has one owner. Each T3 belongs to one platform: Claude's T3s are named `T3-claude-*` and say "Owner:
Claude" at the top; Codex names and writes its own. Neither side builds the other's pieces.

| # | Piece | Owner | Plan | Needs first |
|---|---|---|---|---|
| 1 | The contract: file layout, formats, target rules, versioning | Claude and Codex jointly; Alastair accepts | `docs/contract-v1.md` (not a T3) | T1 agreed |
| 2 | The shared command for the files, and its tests | Claude (proposed; Codex may instead write its own client) | [T3-claude-mail-tool](T3-claude-mail-tool.md) | 1 |
| 3 | Claude's router session | Claude | [T3-claude-router](T3-claude-router.md) | 2 |
| 4 | Skills for every Claude session and the orchestrator, as a plugin | Claude | [T3-claude-session-skills](T3-claude-session-skills.md) | 2 |
| 5 | Codex's side: naming its sessions, noticing mail, delivering it, its skills | Codex | Codex's T3s | 1 (and 2, if Codex uses the command) |
| 6 | The first real round trip, in one project | Claude and Codex, each running its own side; Alastair watches | this T2's acceptance | 3, 4, 5 |

## Order

1. Agree the T1: Alastair and Codex settle the open questions, and Claude amends the T1 to match.
2. Write and agree the contract.
3. Claude builds 2, then 3 and 4. Codex builds 5 at the same time.
4. The round trip (6). Each side tests its own pieces; only the round trip needs both.

## Done when

- A Claude session asks `role:design` in a project a question, and the answer arrives in that same session without it
  polling.
- A Codex session asks `role:orchestrator` a question, and the answer arrives back by whatever means Codex's side uses.
- A message to a channel with listeners on both platforms reaches every listener once.
- A session replaced on a channel receives the mail its predecessor never got.
- Alastair accepts it.

## Out of v1

A viewer page, archiving old mail, closing channels, more platforms than Claude and Codex.


## Codex implementation proposal, 4 November 2026

Draft additions, pending agreement on the [domain review](../docs/reviews/2026-11-04-codex-domain-review.md).
Delivery sequence and acceptance are collected in [M1-first-roundtrip](M1-first-roundtrip.md).

| Piece | Sole T3 owner | Plan | Prerequisite |
|---|---|---|---|
| Scheduled-delivery capability trial | Codex | [T3-codex-capability-trial](T3-codex-capability-trial.md) | Plan acceptance and authorised test chats |
| One global heartbeat relay | Codex | [T3-codex-relay](T3-codex-relay.md) | Passing trial, agreed contract, shared command |
| Codex session skills and live round-trip evidence | Codex | [T3-codex-session-skills](T3-codex-session-skills.md) | Contract and shared command; both relays for live evidence |

Claude's existing three T3s retain sole Claude ownership. Contract agreement is shared review, not a jointly owned
implementation T3. Codex owns its live acceptance report and obtains Claude's evidence without building Claude's side.

Proposed architecture: one manually initialised Codex relay chat, one heartbeat targeting five-minute polling, the
shared global mailbox, and many channel subscriptions mapped to native chat IDs with optional host metadata and
natural-language remits. The relay forwards to selected existing chats; chats reply via the shared command. No automatic
chat creation in v1. Actual cadence, scheduled tool access and busy-chat delivery remain to be proved by the trial.

Proposed correction to Done when: selected recipients receive at least once with deduplication before actions, rather
than a promise of exactly-once transport to every listener. Add empty-channel catch-up and delivered-but-unfinished
handover to acceptance. Durable per-recipient receipts and explicit replay allow restart without repeating completed work.


## Done when, restated for contract v2 (4 November 2026)

The criteria above were written for contract v1: roles, replacement records, relay receipts, a five-minute target.
v2 dropped those. Alastair: "Go ahead" (4 November 2026), on restating the criteria for v2 and closing.

| v2 criterion | Evidence |
|---|---|
| A Claude session asks Codex through a channel and the answer arrives without polling | Messages 25 and 28: the router nudged the asking session, live |
| A Codex session asks Claude and the answer gets back to it | Messages 6, 12 and 16; message 77, with the router waking the Codex chat by `codex queue` |
| Each recipient on a channel is reached once, and one finishing doesn't hide it from another | `test_one_recipient_closing_does_not_hide_anothers_mail`; marks are per recipient in the real mailbox |
| A late joiner picks up waiting mail | Codex's catch-up of the welcome message (registry 10), then a real reply |
| Alastair accepts it | Contract v2 accepted, then "Go ahead" to close |

**Known gaps, carried to T1:** a Codex chat that is busy when nudged is untested, and so are sessions in other
projects. Claude's busy case was seen live: the router reported "queued, session mid-turn" and the mail was handled.
