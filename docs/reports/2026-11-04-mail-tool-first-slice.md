# Mail command, first slice: test report

4 November 2026. Claude. Plan: [T3-claude-mail-tool](../../planning/T3-claude-mail-tool.md), first slice only.
Contract: [contract-v1](../contract-v1.md) draft 3.

## What it is

Claude and Codex can now send each other real messages through one mailbox on this Mac, using one command:
`python3 tool/mail.py`. It is manual: each agent reads and marks its own mail when told to look. Alastair approved this
narrow slice on 4 November ("Yes, minimum slice"). Codex asked for the same scope in paper message
`20261104T165318Z-codex-5572`.

**Supported:** projects, mandates, sessions (register and end), channels, attach with qualifiers (and `--updates` to
change one), detach, explicit catch-up, send, reply, read, mark (read, progress, answered, skipped, closed), inbox,
thread, status.

**Not built, and refused rather than faked:** roles, replace, reroute, retry, presence, leases, relay records, and
routed, attempt and delivered receipts. These wait for the router, the relay and the capability trial.

## Tests

`python3 -m unittest discover tool/tests` ran 11 tests, all passing (13.8 s). Each runs against its own throwaway
mailbox.

| What Codex asked to see | Test | Result |
|---|---|---|
| Send, read and reply | `test_send_read_reply_and_reply_direction` | pass |
| Reply direction: a reply goes to the asker's platform, not back to everyone | same test, plus `test_reply_to_unset_goes_back_to_sender_only` | pass |
| Catch-up for a late joiner, explicit and bounded | `test_attach_is_future_only_and_catch_up_is_explicit`, `test_catch_up_from_message_is_inclusive_and_bounded` | pass |
| One recipient closing doesn't hide another's mail | `test_one_recipient_closing_does_not_hide_anothers_mail` | pass |
| Unique ids, atomic publication, a stable snapshot | `test_sequence_unique_under_concurrent_writers` (24 parallel sends), `test_snapshot_is_fixed_at_send`, `test_records_are_never_overwritten` | pass |
| Crash recovery (both cases in contract section 4) | `test_recovery_after_crashed_writers` | pass |
| Unsupported or invalid input is refused | `test_refusals`, `test_qualifier_update_names_the_binding` | pass |

## The real mailbox

`~/.agent-mail/` now holds:
- project `exfu-agent-messaging`, escalation `claude`;
- a mandate quoting Alastair's go-ahead to Claude;
- Claude's session `claude:local_f978f185-f656-4199-9af8-c39559188065`;
- channel `exfu-agent-messaging.contract`, with Claude attached;
- the welcome message `20261104T165820.597Z-claude-965ab7df` (seq 6), sent to that channel for Codex **before Codex
  attached**, so that Codex's first read tests catch-up.

## Not tested

- A real round trip with Codex. That is Codex's next turn.
- A whole-machine crash. The recovery test simulates the files a crashed process leaves behind.
- Anything automatic. There is no relay yet, so nothing wakes a session.
