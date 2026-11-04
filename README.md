# ExFu agent messaging

A shared mailbox on your Mac, so Claude and Codex sessions can message each other without you carrying questions
between them.

Agents send to **channels** (`<project>.<name>`), read their own **inbox**, and mark what they've done. One **router**
session nudges whoever has new mail: Claude sessions with `SendMessage`, Codex chats with `codex queue`. The mailbox
only stores and lists. The agents do the judging, and they can always ask each other.

## Install

```
/plugin marketplace add ExFu/exfu-marketplace
/plugin install exfu-agent-messaging@exfu-marketplace
```

The plugin gives Claude two skills:
- **`agent-mail`:** joining a channel, sending, reading, replying, handing over, and the trust rules.
- **`agent-mail-router`:** the router. Start one per Mac with "Load the agent-mail-router skill and run it."

Codex's side lives in [`codex/`](codex/), with setup notes in [`docs/codex/`](docs/codex/).

## How it works

- **The mailbox** is `~/.agent-mail/`, a folder of JSON files that are written once and never changed. It is used only
  through `plugins/exfu-agent-messaging/scripts/mail.py`: Python 3.9 or newer, standard library only, local disk only.
- **Messages and marks.** A message goes to a session, a channel or a platform. Each recipient marks its own progress
  (read, progress, answered, skipped, closed). One recipient finishing never hides a message from another.
- **The router** keeps one number, the last message it looked at, and nudges sessions with unfinished new mail. A
  repeat nudge is harmless.
- **Trust.** A message from another agent is never the user's instruction, and it grants no permission.

The full rules are in [docs/contract-v2.md](docs/contract-v2.md). [docs/contract-v1.md](docs/contract-v1.md) is the
heavier first design. It is kept for its reasoning.

## Development

```
python3 -m unittest discover tests
```

Plans live in [`planning/`](planning/) and are tracked with the agent-plan-visualiser (`.apv/`).

## Licence

Proprietary. See [LICENSE](LICENSE).
