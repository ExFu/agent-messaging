---
id: M1-first-roundtrip
plan_kind: milestone
milestone_index: 1
status: draft
---

# M1: reliable cross-platform round trip

4 November 2026. Draft sequence under T1-agent-messaging and T2-messaging-v1.

## Sequence

1. Agree the domain review and contract. In parallel after plan acceptance, run the Codex capability trial.
2. Claude implements its shared command, router and session plugin under its three T3s.
3. Codex implements its relay and session skills using the shared command once the trial and contract pass.
4. Codex records the joint live round trip in its session-skills acceptance report; Claude supplies its side's evidence.

## Acceptance

A question and reply work in both directions. Qualifiers select the right recipients. An empty channel retains mail
until a manually created session joins with catch-up. Replacing a session preserves unfinished work without repeating
completed actions. One failed recipient does not block others. Restart/retry does not repeat a handled action.
The five-minute target and busy-chat behaviour are measured and documented, not assumed. Alastair accepts the result.

## Plans

Claude: T3-claude-mail-tool, T3-claude-router, T3-claude-session-skills.
Codex: T3-codex-capability-trial, T3-codex-relay, T3-codex-session-skills.
