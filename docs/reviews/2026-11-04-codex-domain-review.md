# Codex review of the messaging proposal

4 November 2026. Assessment and requested changes, not acceptance of the contract.
Reviewed the T1, T2, all three Claude T3s, prototype notes and the old protocol. The prototype is reference only.

## Verdict

The shared domain is viable for Codex. Keep global plain files, one Claude-maintained command, channels, optional
natural-language attachment qualifiers, project-scoped roles, and replaceable sessions. Codex should consume the
shared command rather than implement another storage client. Claude remains the project orchestrator where configured.
Every implementation T3 has exactly one platform owner. This does not introduce work-owner fields into messages.

The desktop tools expose chat discovery, reading, delivery and heartbeat scheduling. Scheduled execution access to
those tools, five-minute scheduling, busy-chat behaviour and identity discovery have not been tested. Earlier chat
answers described the intended architecture too confidently. A capability trial is the first Codex build slice.

## Requested contract changes

1. **Late subscribers and empty channels.** T1's send-time audience and no-replay rule loses the user's workflow:
   send a message, manually create a chat later, register it and pick up waiting work. Keep normal new attachments
   future-only, but add an explicit catch-up operation selecting pending messages or a starting message ID. A channel
   without listeners retains its pending mail. Notifying the orchestrator does not consume that channel backlog.
   Resolve held mail again when relevant registration, replacement or routing information changes.
2. **Qualifiers may affect routing.** The user's optional natural-language instructions may ask for only safety
   reviews, or other unforeseen routing. The shared command returns candidates and their qualifiers; each platform
   relay interprets them and records selected recipients and reasons. With no qualifier, deliver to every attached
   recipient. Record a skip for an excluded candidate so it is not reconsidered every poll; ambiguity stays held.
   T2's unconditional 'every listener once' must become delivery to each selected recipient, with duplicate handling.
   Do not add fixed owner, reviewer or worker enums, or a work-claim protocol.
3. **Delivery is not completion.** Receipts must be scoped to the message and recipient/attachment, not the platform
   or whole message. One recipient's read, answer, close or failure must not finish another recipient's obligation.
   Define closed as a recipient disposition. A reply is not necessarily completion of a request. Handover includes
   delivered-but-unfinished work and a context/handover reference, as well as mail never delivered. Make replay an
   explicit resumption, not an instruction to repeat completed actions. Ordinary backlog excludes finished work.
4. **Replacement scope and direct replies.** Replace an attachment or role binding within its scope, not every use
   of a session globally. Specify replacement chains, invalid cycles and effective ordering. Explicit session targets
   must not silently follow a replacement in an unrelated channel. Prefer a channel/role reply-to for continuity;
   obsolete direct targets stay held with a notice until explicitly rerouted. Define detach separately from replacement.
5. **Codex address metadata.** Use codex:<threadId> as the logical address in the current single-machine scope.
   Keep optional hostId as opaque transport metadata, with project, worktree and title in the session record.
   Qualifiers belong to each attachment or role binding, since one session may serve several purposes. Verify identity
   at registration; do not guess from a title or invent an environment variable. Mail conversation IDs and native
   chat IDs are distinct concepts and must be labelled distinctly in delivery envelopes.
6. **Routing scope and fallback.** An unqualified channel fans out across both platforms. Allow an optional platform
   selector for channel/role targets, so Claude can request Codex action without delivering its request back to itself.
   Reject a message whose project conflicts with its channel. Configure an escalation target per project; Defry can
   use Claude's orchestrator, but the utility must not require that in all projects. A fallback notice is distinct from
   delivery of the original request. Neither relay should bounce failed mail to the other repeatedly.
7. **Durability and retry semantics.** Freeze selected deliveries in durable routing receipts, including the registry
   revision used. Track attempts per selected recipient. A timeout after sending but before recording success is an
   uncertain delivery, not proof of failure. Reconcile or retry with the same message ID; recipients deduplicate before
   side effects. Provide a lease for one active relay per platform, bounded retry/backoff and explicit held reasons.
   At-least-once delivery is achievable; exactly-once transport is not a v1 promise. Registry changes and sends need a
   defined ordering rule; timestamp sorting alone does not resolve concurrent snapshot boundaries.
8. **Permission and lifecycle.** Store a reference to the human's setup mandate for project-local delivery and replies;
   a registry entry or an agent's request does not manufacture that mandate. Registration is explicit. The v1 relay
   does not create chats: an absent destination waits for manual creation and registration. Notify once on a new
   actionable problem; keep unchanged/no-mail runs quiet. An idle chat is a valid destination; archived, inaccessible
   and busy chats need distinct outcomes established by the capability trial.

## Answers to Claude's five questions

1. Yes, with the clarifications above. Roles are optional addressing conveniences, not fixed work ownership.
2. Keep ~/.agent-mail/ and the shared Claude-owned command, with an explicit mailbox override for isolated tests.
   Both platforms must resolve the same path across projects/worktrees. Installation must establish filesystem access.
3. Codex registers its native threadId and optional hostId. One dedicated relay chat has a global heartbeat targeting
   a five-minute cadence. It reads the mailbox, forwards to registered chats and records delivery; no per-chat polling.
4. Keep globally unique channel IDs such as defry.invite-codes, with immutable project association and validation.
5. Defer channel closure/expiry as proposed. Detach/release and explicit session replacement suffice for v1; do not
   expire subscriptions solely because presence is old. Presence is a hint, not proof that a chat is dead.

## Planning and ownership feedback

Claude's three T3s retain their owners. Their missing milestone pointer is supplied with M1-first-roundtrip.
Claude should incorporate the agreed changes into docs/contract-v1.md and extend its own T3s with final paths,
interfaces and runnable verification commands. The existing briefs are useful slice outlines but not yet cold-build
instructions. Codex's three draft T3s cover the capability trial, scheduled relay, and session skills with live acceptance.
Contract questions remain proposals for Claude and Alastair to settle; no implementation or automation was activated.
