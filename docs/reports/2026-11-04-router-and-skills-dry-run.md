# Router and session skills: dry run

4 November 2026. Claude. Plans: [T3-claude-router](../../planning/T3-claude-router.md) slice 2 and
[T3-claude-session-skills](../../planning/T3-claude-session-skills.md) slice 2.

## What was run

Two fresh subagents each followed one skill cold, against its own throwaway mailbox. The real `~/.agent-mail/` was
never touched. In the router run, liveness checks and deliveries were simulated: a session named "gone" was "not
found", and each delivery was written to a file instead of being sent.

## Results

**Router**: all five scenarios came out as the rules say.
- **Channel request, three Claude listeners:**
  - delivered to the one whose qualifier matched (copy and layout);
  - skipped for the security-only listener;
  - held for the dead session, to be retried in an hour.
- **Codex's reply to a Claude question:** delivered to the asker, skipped by qualifier for the other listener, and held
  for the dead one.
- **Bare `claude` mail with no Claude session in the thread:** held for placing by hand.
- **Mail meant for Claude with no Claude listener:** held as unplaced.
- **A delivery left half-done by a crashed router:** marked uncertain, retried as attempt 2, then delivered.

The queue ended empty. A message the recipient had already read by hand never entered the queue.

**Session skill**: the session joined the channel and caught up. It read the waiting question, replied, and closed it.
It then asked Codex a question whose answer is set to come back to Claude listeners only. It did not wait for the
answer.

## Fixed after the run

**In the command:**
- `read` now says whether a message is new, unfinished or already finished. Before, a first read showed "read" as if
  the work had been resumed.
- The read header separates who a message went to from where replies go.
- `send` echoes its routing.
- `catch-up` reports how many messages it brought.
- There is a new `mandates` listing.
- Uncertain deliveries no longer use up the three-attempt budget. That was a contract mismatch.

**In the router skill:**
- The lease generation goes in a plain variable, and the lease is renewed before every send.
- The liveness check always comes first, and its result wins.
- Each session is checked once per pass.
- A reply goes to the session that asked.
- Every hold and skip gets a transcript line.

**In the session skill:**
- Option placement is explained.
- It says how to find a mandate.
- `inbox` after a catch-up is spelled out.
- `status`, `thread` and `inbox --all` are in the quick reference.
- The quick-reference wording about reply direction is clearer.

**Tests:** 20, all passing (`python3 -m unittest discover tool/tests`).

## Not yet done

- A live run (router T3, slice 3): a real router session delivering into real Claude sessions, with Alastair watching.
- Installing the plugin, and choosing its marketplace.
