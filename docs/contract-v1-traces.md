# Contract v1: worked traces

Date: 4 November 2026. Status: **draft, paper fixture** for [contract-v1](contract-v1.md) draft 2. Requested by Codex
in message `20261104T163452Z-codex-7600`. Every identity here is **simulated** (`sim-…`) and exists only on this page,
not in any registry. Records are cut to the fields that matter. `seq` is the mailbox sequence (contract section 3).

"Open obligations" lists every (message, recipient) pair with `routed` and neither `closed` nor `transferred`,
after each step.

## Trace A: two recipients; one closes, one stays unfinished

Project `demo`, escalation `role:orchestrator`. A third candidate is skipped by its qualifier.

| seq | Record | Detail | Open obligations after |
|---|---|---|---|
| 1 | registry `project` | `demo`, escalation `role:orchestrator` | none |
| 2 | registry `channel` | `demo.unlock`, purpose "the unlock screen rebuild" | none |
| 3 | registry `session` | `claude:sim-ana` | none |
| 4 | registry `session` | `claude:sim-cy` | none |
| 5 | registry `session` | `codex:sim-ben` | none |
| 6 | registry `session` | `codex:sim-dee` (the sender) | none |
| 7 | registry `attach` | `demo.unlock`, `claude:sim-ana`, qualifier "the screen's copy and layout" | none |
| 8 | registry `attach` | `demo.unlock`, `claude:sim-cy`, qualifier "only safety reviews" | none |
| 9 | registry `attach` | `demo.unlock`, `codex:sim-ben`, no qualifier | none |
| 10 | message `M1` | from `codex:sim-dee`, to `channel:demo.unlock`, platform null, `request`: "Shorten the unlock button label; the old one wraps on small phones." `registry_revision` 9 | none (not yet routed) |
| 11 | receipt `routed` | M1 → `claude:sim-ana`, via `channel:demo.unlock`, note "copy change matches 'copy and layout'", rev 9 | M1/ana |
| 12 | receipt `skipped` | M1 → `claude:sim-cy`, note "a label change is not a safety review", rev 9 | M1/ana |
| 13 | receipt `routed` | M1 → `codex:sim-ben`, via `channel:demo.unlock`, note "no qualifier", rev 9 | M1/ana, M1/ben |
| 14 | receipt `attempt-started` | M1 → ana, `attempt_id` a1, attempt 1 | M1/ana, M1/ben |
| 15 | receipt `delivered` | M1 → ana, `attempt_id` a1 | M1/ana, M1/ben |
| 16 | receipt `attempt-started` | M1 → ben, `attempt_id` b1, attempt 1 | M1/ana, M1/ben |
| 17 | receipt `delivered` | M1 → ben, `attempt_id` b1 | M1/ana, M1/ben |
| 18 | receipt `read` | M1, recipient ana | M1/ana, M1/ben |
| 19 | receipt `read` | M1, recipient ben | M1/ana, M1/ben |
| 20 | message `R1` | from ana, `reply` in M1's thread: "Done: label is now 'Unlock'." to `channel:demo.unlock`, platform `codex` (M1's `reply_platform` defaulted to the sender's platform) | M1/ana, M1/ben |
| 21 | receipt `answered` | M1, recipient ana, `ref` R1 | M1/ana, M1/ben |
| 22 | receipt `closed` | M1, recipient ana, note "label changed and verified" | M1/ben |
| 23 | receipt `progress` | M1, recipient ben, note "Codex-side string updated; tests not yet run" | M1/ben |

**Checks.**
- Ana's `closed` (22) closes only M1/ana. M1/ben stays open: Ben is unfinished, with progress recorded.
- Cy was a candidate but never had an obligation, so Cy appears in no "open" column, then or later.
- R1 (20) goes to Codex listeners on the channel (Ben). It doesn't come back to Claude listeners (Ana, Cy), because
  the reply took `platform: codex` from M1's `reply_platform`. Its audience is worked out at R1's own `seq`.
- If Ben's session dies now, nothing is lost. M1/ben is open and its progress note is on record, ready for a
  `replace` (Trace B).

## Trace B: replacing one channel binding while another stays

Session `claude:sim-old` listens on two channels. Its context runs out. Alastair replaces it on `demo.design` only.

| seq | Record | Detail | Open obligations after |
|---|---|---|---|
| 1–3 | registry `project`, `channel` ×2 | `demo`; `demo.design`; `demo.backend` | none |
| 4 | registry `session` | `claude:sim-old` | none |
| 5 | registry `session` | `codex:sim-ben` | none |
| 6 | registry `attach` | `demo.design`, old, qualifier "screens, not icons" | none |
| 7 | registry `attach` | `demo.backend`, old, no qualifier | none |
| 8 | registry `attach` | `demo.design`, ben, no qualifier | none |
| 9 | message `M2` | to `channel:demo.design`, platform `claude`: "Redo the settings screen spacing." rev 8 | none |
| 10 | receipt `routed` | M2 → old, via `channel:demo.design`, rev 8 | M2/old |
| 11 | receipts `attempt-started`, `delivered` | M2 → old (shown as one row) | M2/old |
| 12 | receipt `progress` | M2, old: "spacing tokens changed; screenshots not taken" | M2/old |
| 13 | message `M3` | to `channel:demo.design`, platform null: "New app icon sizes." rev 12 | M2/old |
| 14 | receipt `skipped` | M3 → old, note "icons excluded by qualifier" | M2/old |
| 15 | receipt `routed` | M3 → ben, via `channel:demo.design` | M2/old, M3/ben |
| 16 | message `M4` | to `channel:demo.backend`: "Rotate the test API key." rev 15 | M2/old, M3/ben |
| 17 | receipt `routed` | M4 → old, via `channel:demo.backend`, rev 15 | M2/old, M3/ben, M4/old |
| 18 | receipts `attempt-started`, `delivered`, `read` | M4 → old | M2/old, M3/ben, M4/old |
| 19 | registry `session` | `claude:sim-new` | M2/old, M3/ben, M4/old |
| 20 | registry `replace` | scope `channel:demo.design`, old → new, `handover` "old's summary at <reference>" | M2/old, M3/ben, M4/old (the relay hasn't acted yet) |
| 21 | receipt `routed` | M2 → new, via `channel:demo.design`, note "takes over M2/old (receipt 10) under replace 20; resume from progress 12", rev 20 | M2/old (transferred), M2/new, M3/ben, M4/old |
| 22 | receipt `transferred` | M2, recipient old, by the relay, `ref` replace 20 | M2/new, M3/ben, M4/old |
| 23 | message `M5` | to `channel:demo.design`, platform `claude`: "Check dark mode." rev 22 | M2/new, M3/ben, M4/old |
| 24 | receipt `routed` | M5 → new (old's binding on this channel followed through replace 20), rev 22 | M2/new, M3/ben, M4/old, M5/new |

**Checks.**
- **Delivered-but-unfinished work transfers.** M2 was delivered and part-done (12). It moves to New (21), with the
  progress note and handover reference, so New resumes from where Old stopped.
- **A skipped candidate does not transfer.** Old was skipped for M3 (14), so New gets nothing for M3. M3/ben is
  untouched.
- **Another binding stays intact.** M4 came via `demo.backend`. The replacement was scoped to `demo.design`, so M4/old
  stays with Old, and Old still listens on `demo.backend`.
- **Future mail follows the replacement** in that scope only (24).

**What this trace changed in the contract.** Writing row 22 showed that draft 2 never said how Old's obligation ends.
A relay writing `closed` for Old would break "handled means closed", because Old never finished it. So the contract
now has a `transferred` disposition. It is written by the relay and cites the `replace`, and it ends an obligation
without claiming it was finished.
