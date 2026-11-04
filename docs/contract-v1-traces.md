# Contract v1: worked traces

Date: 4 November 2026. Status: **draft, paper fixture** for [contract-v1](contract-v1.md) draft 3. Requested by Codex
in message `20261104T163452Z-codex-7600`, and corrected after its check in `20261104T164344Z-codex-7b2c`. Every
identity here is **simulated** (`sim-…`) and exists only on this page, not in any registry. Records are cut to the
fields that matter.

How to read the tables:
- Every row is **one published record** with its own `seq` (contract section 3).
- `rev` is a message's or receipt's `registry_revision`: the `seq` of the newest **registry** record below it.
- "Open obligations" lists every (message, recipient) pair with `routed` and neither `closed` nor `transferred`,
  after that row.

## Trace A: two recipients; one closes, one stays unfinished

Project `demo`, escalation `role:orchestrator`. A third candidate is skipped by its qualifier. The sender, Dee, is
**not** attached to the channel, and so does not receive the channel reply.

| seq | Record | Detail | Open obligations after |
|---|---|---|---|
| 1 | registry `project` | `demo`, escalation `role:orchestrator` | none |
| 2 | registry `channel` | `demo.unlock`, purpose "the unlock screen rebuild" | none |
| 3 | registry `session` | `claude:sim-ana` | none |
| 4 | registry `session` | `claude:sim-cy` | none |
| 5 | registry `session` | `codex:sim-ben` | none |
| 6 | registry `session` | `codex:sim-dee` (the sender) | none |
| 7 | registry `attach` | `demo.unlock`, ana, qualifier "the screen's copy and layout" | none |
| 8 | registry `attach` | `demo.unlock`, cy, qualifier "only safety reviews" | none |
| 9 | registry `attach` | `demo.unlock`, ben, no qualifier | none |
| 10 | message `M1` | from dee, to `channel:demo.unlock`, platform null, **`reply_to: channel:demo.unlock`, `reply_platform: codex`**, `request`: "Shorten the unlock button label; the old one wraps on small phones." rev 9 | none (not yet routed) |
| 11 | receipt `routed` | M1 → ana, via `channel:demo.unlock`, note "copy change matches 'copy and layout'", rev 9 | M1/ana |
| 12 | receipt `skipped` | M1 → cy, note "a label change is not a safety review", rev 9 | M1/ana |
| 13 | receipt `routed` | M1 → ben, via `channel:demo.unlock`, note "no qualifier", rev 9 | M1/ana, M1/ben |
| 14 | receipt `attempt-started` | M1 → ana, `attempt_id` a1, attempt 1, rev 9 | M1/ana, M1/ben |
| 15 | receipt `delivered` | M1 → ana, `attempt_id` a1, rev 9 | M1/ana, M1/ben |
| 16 | receipt `attempt-started` | M1 → ben, `attempt_id` b1, attempt 1, rev 9 | M1/ana, M1/ben |
| 17 | receipt `delivered` | M1 → ben, `attempt_id` b1, rev 9 | M1/ana, M1/ben |
| 18 | receipt `read` | M1, recipient ana, rev 9 | M1/ana, M1/ben |
| 19 | receipt `read` | M1, recipient ben, rev 9 | M1/ana, M1/ben |
| 20 | message `R1` | from ana, `reply` to M1: "Done: label is now 'Unlock'." `to: channel:demo.unlock` and `platform: codex`, both copied from M1's `reply_to` and `reply_platform`. rev 9 | M1/ana, M1/ben |
| 21 | receipt `answered` | M1, recipient ana, `ref` R1, rev 9 | M1/ana, M1/ben |
| 22 | receipt `closed` | M1, recipient ana, note "label changed and verified", rev 9 | M1/ben |
| 23 | receipt `progress` | M1, recipient ben, note "Codex-side string updated; tests not yet run", rev 9 | M1/ben |

**Checks.**
- Ana's `closed` (22) closes only M1/ana. M1/ben stays open: Ben is unfinished, with progress recorded.
- Cy was a candidate but never had an obligation, so Cy appears in no "open" column, then or later.
- **R1's audience** is worked out at R1's own `seq` (20), from the registry up to rev 9. It goes to Codex listeners on
  `demo.unlock`: that is Ben only. Ana and Cy are excluded by `platform: codex`. Dee is excluded because Dee is not
  attached. Had M1 left `reply_to` unset, it would have defaulted to `codex:sim-dee`, and R1 would have gone to Dee
  directly and to nobody else.
- If Ben's session dies now, nothing is lost. M1/ben is open and its progress note is on record, ready for a
  `replace` (Trace B).

## Trace B: replacing one channel binding while another stays

Session `claude:sim-old` listens on two channels. Its context runs out, so it has stopped (contract section 10, "When
to replace"). Alastair replaces it on `demo.design` only.

| seq | Record | Detail | Open obligations after |
|---|---|---|---|
| 1 | registry `project` | `demo` | none |
| 2 | registry `channel` | `demo.design` | none |
| 3 | registry `channel` | `demo.backend` | none |
| 4 | registry `session` | `claude:sim-old` | none |
| 5 | registry `session` | `codex:sim-ben` | none |
| 6 | registry `attach` | `demo.design`, old, qualifier "screens, not icons" | none |
| 7 | registry `attach` | `demo.backend`, old, no qualifier | none |
| 8 | registry `attach` | `demo.design`, ben, no qualifier | none |
| 9 | message `M2` | to `channel:demo.design`, platform `claude`: "Redo the settings screen spacing." rev 8 | none |
| 10 | receipt `routed` | M2 → old, via `channel:demo.design`, rev 8 | M2/old |
| 11 | receipt `attempt-started` | M2 → old, `attempt_id` o1, rev 8 | M2/old |
| 12 | receipt `delivered` | M2 → old, `attempt_id` o1, rev 8 | M2/old |
| 13 | receipt `progress` | M2, recipient old: "spacing tokens changed; screenshots not taken", rev 8 | M2/old |
| 14 | message `M3` | to `channel:demo.design`, platform null: "New app icon sizes." rev 8 | M2/old |
| 15 | receipt `skipped` | M3 → old, note "icons excluded by qualifier", rev 8 | M2/old |
| 16 | receipt `routed` | M3 → ben, via `channel:demo.design`, rev 8 | M2/old, M3/ben |
| 17 | message `M4` | to `channel:demo.backend`: "Rotate the test API key." rev 8 | M2/old, M3/ben |
| 18 | receipt `routed` | M4 → old, via `channel:demo.backend`, rev 8 | M2/old, M3/ben, M4/old |
| 19 | receipt `attempt-started` | M4 → old, `attempt_id` o2, rev 8 | M2/old, M3/ben, M4/old |
| 20 | receipt `delivered` | M4 → old, `attempt_id` o2, rev 8 | M2/old, M3/ben, M4/old |
| 21 | receipt `read` | M4, recipient old, rev 8 | M2/old, M3/ben, M4/old |
| 22 | registry `session` | `claude:sim-new` | M2/old, M3/ben, M4/old |
| 23 | registry `replace` (id `X23`) | scope `channel:demo.design`, old → new, `handover` "old's summary at <reference>" | M2/old (**barred**: old must not act on it from here), M3/ben, M4/old |
| 24 | receipt `routed` | M2 → new, via `channel:demo.design`, `handover {replace: X23, source: receipt 10}`, rev 23 | M2/old (barred), M2/new, M3/ben, M4/old |
| 25 | receipt `transferred` | M2, recipient old, same `handover`, rev 23 | M2/new, M3/ben, M4/old |
| 26 | message `M5` | to `channel:demo.design`, platform `claude`: "Check dark mode." rev 23 | M2/new, M3/ben, M4/old |
| 27 | receipt `routed` | M5 → new (old's binding on this channel followed through X23), rev 23 | M2/new, M3/ben, M4/old, M5/new |

Rows 24 and 25 are published in **one exclusive-lock hold** (contract section 10), so no reader ever sees one without
the other.

**Checks.**
- **Delivered-but-unfinished work transfers.** M2 was delivered and part done (13). It moves to New (24), with the
  progress note and handover reference, so New resumes from where Old stopped.
- **The replace bars Old at once.** From row 23, Old must not act on M2, even before rows 24 and 25 exist. In the gap
  between rows 23 and 24 there is one open obligation on paper, but nobody is allowed to act on it.
- **A skipped candidate does not transfer.** Old was skipped for M3 (15), so New gets nothing for M3. M3/ben is
  untouched.
- **Another binding stays intact.** M4 came via `demo.backend`. The replacement was scoped to `demo.design`, so M4/old
  stays with Old, and Old still listens on `demo.backend`.
- **Future mail follows the replacement** in that scope only (27).
- **Repeating rows 24–25 is harmless.** The handover identity `{X23, receipt 10}` is already used, so the command
  refuses a second successor. A crash between them is completed by recovery.
- **Racing a close.** Had Old written `closed` for M2 before row 24, M2 would count as finished and would not
  transfer. After row 25, the command refuses Old's `closed` for M2.
