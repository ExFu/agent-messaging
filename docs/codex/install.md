# Local Codex prototype

This implementation uses contract v2 (`agent-mail/2`) and the repository's shared `tool/mail.py`. It adds no mailbox implementation or Claude plugin changes.

To join a session, ask it to read `codex/skills/agent-mail/SKILL.md` from this checkout. The router heartbeat reads `codex/skills/agent-mail-relay/SKILL.md` by absolute path. These are working repository instructions, not globally installed skills; global distribution and second-project installation remain future work. Set AGENT_MAIL_CMD if moving the shared tool, and update the saved heartbeat prompt accordingly.

The mailbox is outside the usual project sandbox. Use the normal approval mechanism for the shared tool, including reads. No secret data belongs in the mailbox. Joining does not authorise arbitrary cross-chat messages: the user must authorise the destinations.
