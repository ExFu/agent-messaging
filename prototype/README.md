# Prototype: Claude's first pass (not agreed, not an implementation)

Parked here on 3 November 2026 when the work moved out of the defry repository. Alastair: "at this stage, we should be
in planning mode and not implementing anything, as we haven't yet agreed with Codex on the viability of the domain
models!" The design under discussion is [planning/T1-agent-messaging.md](../planning/T1-agent-messaging.md). Use these
files as reference for that discussion only. Do not install the skills or run the tool against the real `~/.agent-mail/`.

| Path | What it is | State |
|---|---|---|
| `first-pass/T3-agent-mail-v1.md` | The first plan: one mailbox per repository, session addresses, a Claude router, the orchestrator as catch-all. | Superseded by the T1. |
| `first-pass/protocol-v1.md` | The first wire format (`agent-mail/1`) and command list. | Superseded: no channels, roles or projects. |
| `tool/mail.py` | A stdlib Python command for the shared files, half moved to the T1 model (`agent-mail/2`): a machine-wide mailbox, projects, channels with attachments and qualifiers, roles per project, replacements, an orchestrator fallback. | Mid-rewrite when work stopped. Never run against real mail. |
| `tool/tests/test_mail.py` | Tests for the first version (19, all passing against it). | Out of date: they fail against the half-rewritten tool. |
| `claude-skills/agent-mail/` | Draft skill for every Claude session. | First-pass model: no channels or roles. |
| `claude-skills/agent-mail-router/` | Draft skill for Claude's router session, revised after one dry run. | First-pass model: no channels or roles. |
