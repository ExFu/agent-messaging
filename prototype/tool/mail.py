#!/usr/bin/env python3
"""Agent mail: one mailbox on this Mac for Claude and Codex sessions (planning/T3-agent-mail.md, docs/agent-mail.md).

    python3 scripts/agent-mail/mail.py whoami
    python3 scripts/agent-mail/mail.py hello --title "Invite codes" --topics "invite unlock screen, T3-invite-only"
    python3 scripts/agent-mail/mail.py channel create defry.invite-codes --purpose "Invite code work: status and questions"
    python3 scripts/agent-mail/mail.py attach defry.invite-codes --qualifiers "the unlock screen and its copy"
    python3 scripts/agent-mail/mail.py role claim orchestrator --qualifiers "plans and farms out unowned work"
    python3 scripts/agent-mail/mail.py send --to role:orchestrator --kind request --subject "..." --body-file q.md
    python3 scripts/agent-mail/mail.py reply <id> --body "Use KitCard."
    python3 scripts/agent-mail/mail.py pending --for claude          # an observer's queue
    python3 scripts/agent-mail/mail.py watch --for claude --once     # exits when that queue is not empty

The mailbox is a folder of small JSON files, `~/.agent-mail/` (or `$AGENT_MAIL_DIR`), shared by every project on the
Mac; messages, channels and roles each name their project. Nothing is ever changed in place: a message is written once,
what happens to it is a receipt beside it, and channels, attachments and roles are events in an append-only registry.
Every write is a temporary file renamed into place, so two agents writing at once never clobber each other.

Targets: `claude:<session>` or `codex:<session>` (one session), `claude` or `codex` (that platform's observer decides),
`role:<name>` (whoever holds the role in the message's project), `channel:<id>` (every session attached to it).

Your own address comes from `$AGENT_MAIL_FROM`, or else `claude:$CLAUDE_CODE_HOST_SESSION_ID` (the Claude desktop app
sets it in every session). Your project comes from `$AGENT_MAIL_PROJECT`, or else the main checkout's folder name.
Stdlib only, Python 3.9 or newer.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "agent-mail/2"
PLATFORMS = ("claude", "codex")
KINDS = ("ask", "request", "tell", "reply")
WANTS_REPLY = {"ask": True, "request": True, "tell": False, "reply": False}
EVENTS = ("routed", "held", "delivered", "failed", "read", "answered", "delegated", "closed")
# A target is done once one of these names it (`instead_of` counts: delivered to the fallback in its place).
TARGET_DONE = ("delivered", "closed")
# A message stops being unread for a reader once the reader's platform records one of these.
READER_DONE = ("read", "answered", "closed")
FALLBACK_ROLE = "orchestrator"
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
ENVELOPE_BODY_LIMIT = 6000


class MailError(Exception):
    pass


# Paths, identity and names


def git(*args: str, cwd: Path | None = None) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def mail_root() -> Path:
    root = Path(os.environ.get("AGENT_MAIL_DIR") or "~/.agent-mail").expanduser()
    for sub in ("messages", "receipts", "registry", "presence", "tmp"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def my_address() -> str:
    explicit = os.environ.get("AGENT_MAIL_FROM")
    if explicit:
        return check_address(explicit)
    host = os.environ.get("CLAUDE_CODE_HOST_SESSION_ID")
    if host:
        return f"claude:{host}"
    raise MailError("cannot tell who you are: set AGENT_MAIL_FROM to <platform>:<session id>")


def my_project() -> str:
    explicit = os.environ.get("AGENT_MAIL_PROJECT")
    if explicit:
        return check_name(explicit, "project")
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    if common is None:
        raise MailError("not inside a git checkout: pass --project or set AGENT_MAIL_PROJECT")
    return check_name(Path(common).parent.name.lower(), "project")


def check_name(name: str, what: str) -> str:
    if not NAME.match(name):
        raise MailError(f"{what} {name!r} must be lower-case letters, digits, '.', '_' or '-'")
    return name


def check_address(address: str) -> str:
    platform, sep, rest = address.partition(":")
    if platform not in PLATFORMS or not sep or not rest or ":" in rest or "/" in rest or rest != rest.strip():
        raise MailError(f"{address!r} is not a session address (<platform>:<session id>)")
    return address


def check_target(target: str) -> str:
    if target in PLATFORMS:
        return target
    kind, _, name = target.partition(":")
    if kind in ("role", "channel"):
        check_name(name, kind)
        return target
    return check_address(target)


def platform_of(address: str) -> str:
    return address.partition(":")[0]


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def stamp(at: dt.datetime) -> str:
    return at.strftime("%Y%m%dT%H%M%S") + f"{at.microsecond // 1000:03d}Z"


def iso(at: dt.datetime) -> str:
    return at.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_json(root: Path, path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = root / "tmp" / f"{path.name}.{os.getpid()}.{secrets.token_hex(3)}"
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # gone, or not ours: skip rather than crash a watcher


def read_folder(folder: Path) -> list[dict]:
    if not folder.is_dir():
        return []
    found = (read_json(p) for p in sorted(folder.glob("*.json")))
    return [x for x in found if x]


# The registry: channels, attachments and roles, folded from append-only events


def record(root: Path, op: str, kind: str, name: str, project: str, **fields) -> dict:
    at = now()
    event = {"op": op, "kind": kind, "name": name, "project": project, "by": my_address(), "at": iso(at)}
    event.update({k: v for k, v in fields.items() if v})
    write_json(root, root / "registry" / f"{stamp(at)}-{secrets.token_hex(3)}.json", event)
    return event


def registry(root: Path, until: str | None = None) -> dict:
    """The registry as it stood at `until` (an ISO time), or now. Channels by id; attachments by channel, then
    address; roles by (project, name), then address; and `replaced`, old address to new, per channel or role."""
    state: dict = {"channels": {}, "attached": {}, "roles": {}, "replaced": {}}
    for e in read_folder(root / "registry"):
        if until and e["at"] > until:
            break
        key = e["name"] if e["kind"] == "channel" else (e["project"], e["name"])
        holders = state["attached"] if e["kind"] == "channel" else state["roles"]
        if e["op"] == "create":
            state["channels"][e["name"]] = {k: e.get(k) for k in ("name", "project", "qualifiers", "by", "at")}
        elif e["op"] in ("attach", "claim"):
            holders.setdefault(key, {})[e["address"]] = {k: e.get(k) for k in ("address", "qualifiers", "by", "at")}
            if e.get("replaces"):
                holders.get(key, {}).pop(e["replaces"], None)
                state["replaced"].setdefault((e["kind"], key), {})[e["replaces"]] = e["address"]
        elif e["op"] in ("detach", "release"):
            holders.get(key, {}).pop(e["address"], None)
    return state


def replacement(state: dict, kind: str, key, address: str) -> str:
    seen = {address}
    swaps = state["replaced"].get((kind, key), {})
    while address in swaps and swaps[address] not in seen:
        address = swaps[address]
        seen.add(address)
    return address


def role_holders(state: dict, project: str, role: str) -> dict:
    return state["roles"].get((project, role), {})


# Messages and receipts


def new_id(sender: str) -> str:
    return f"{stamp(now())}-{platform_of(sender)}-{secrets.token_hex(2)}"


def make_message(sender: str, to: str, kind: str, subject: str, body: str, *, project: str, thread: str | None = None,
                 in_reply_to: str | None = None, reply_to: str | None = None, context: dict | None = None,
                 wants_reply: bool | None = None) -> dict:
    if kind not in KINDS:
        raise MailError(f"kind must be one of {', '.join(KINDS)}")
    if not subject.strip():
        raise MailError("a message needs a subject")
    if not body.strip():
        raise MailError("a message needs a body")
    msg_id = new_id(sender)
    return {
        "schema": SCHEMA,
        "id": msg_id,
        "project": check_name(project, "project"),
        "thread": thread or msg_id,
        "in_reply_to": in_reply_to,
        "from": check_address(sender),
        "to": check_target(to),
        "reply_to": check_target(reply_to or sender),
        "kind": kind,
        "wants_reply": WANTS_REPLY[kind] if wants_reply is None else wants_reply,
        "subject": subject.strip(),
        "body": body,
        "context": context or {},
        "created_at": iso(now()),
    }


def post(root: Path, msg: dict) -> dict:
    write_json(root, root / "messages" / f"{msg['id']}.json", msg)
    return msg


def load_message(root: Path, msg_id: str) -> dict:
    msg = read_json(root / "messages" / f"{msg_id}.json")
    if msg is None:
        raise MailError(f"no message {msg_id}")
    return msg


def all_messages(root: Path) -> list[dict]:
    return read_folder(root / "messages")


def receipts(root: Path, msg_id: str) -> list[dict]:
    return read_folder(root / "receipts" / msg_id)


def add_receipt(root: Path, msg_id: str, event: str, by: str, **fields: str | None) -> dict:
    if event not in EVENTS:
        raise MailError(f"event must be one of {', '.join(EVENTS)}")
    at = now()
    receipt = {"event": event, "by": by, "at": iso(at)}
    receipt.update({k: v for k, v in fields.items() if v})
    write_json(root, root / "receipts" / msg_id / f"{stamp(at)}-{event}-{secrets.token_hex(2)}.json", receipt)
    return receipt


# Resolving a message's targets


def resolve(root: Path, msg: dict, state: dict | None = None) -> dict:
    """Who a message is for. Channels and roles are read as they stood when it was sent, so attaching later does not
    replay old mail; then each address is followed through any replacement made since, so a session that took over a
    channel or role from a dead one gets what the dead one never received.

    `mode` is "targets" (with `targets`), "platform" (`to` is a bare platform: its observer decides), or "unplaced"
    (nobody holds the role or channel, nor the orchestrator role in the message's project)."""
    to = msg["to"]
    now_state = state or registry(root)
    if to in PLATFORMS:
        return {"mode": "platform", "platform": to, "targets": []}
    if platform_of(to) in PLATFORMS:
        return {"mode": "targets", "targets": [{"address": to, "rule": "addressed", "via": to}]}
    then = registry(root, until=msg["created_at"])
    kind, _, name = to.partition(":")
    key = name if kind == "channel" else (msg["project"], name)
    held = (then["attached"] if kind == "channel" else then["roles"]).get(key, {})
    rule = kind
    if not held and to != f"role:{FALLBACK_ROLE}":
        key, kind, name, rule = (msg["project"], FALLBACK_ROLE), "role", FALLBACK_ROLE, "fallback"
        held = role_holders(then, *key)
    if not held and kind == "role" and name == FALLBACK_ROLE:
        held = role_holders(now_state, *key)  # mail that waited for an orchestrator goes to the one there is now
    if not held:
        return {"mode": "unplaced", "targets": [],
                "reason": f"nobody holds {to}" + ("" if to == f"role:{FALLBACK_ROLE}" else f" or role:{FALLBACK_ROLE}")
                + f" in {msg['project']}"}
    current = now_state["attached"] if kind == "channel" else now_state["roles"]
    via = f"channel:{key}" if kind == "channel" else f"role:{key[1]}"
    out, seen = [], set()
    for address, reg in held.items():
        live = replacement(now_state, kind, key, address)
        if live in seen:
            continue
        seen.add(live)
        reg = current.get(key, {}).get(live, reg)
        target = {"address": live, "rule": rule, "via": via, "qualifiers": reg.get("qualifiers")}
        if live != address:
            target["replaces"] = address
        out.append(target)
    return {"mode": "targets", "targets": out}


def target_done(rcpts: list[dict], address: str) -> bool:
    return any(r["event"] in TARGET_DONE and (r.get("target") == address or r.get("instead_of") == address
                                               or (r["event"] == "closed" and not r.get("target")))
               for r in rcpts)


def work_for(root: Path, msg: dict, platform: str, state: dict) -> dict | None:
    """What `platform`'s observer still has to do for a message: None, or the resolution with only its own undone
    targets left in. Unplaced mail is every observer's to hold until someone can take it."""
    rcpts = receipts(root, msg["id"])
    res = resolve(root, msg, state)
    if res["mode"] == "targets":
        mine = [t for t in res["targets"] if platform_of(t["address"]) == platform and not target_done(rcpts, t["address"])]
        return {**res, "targets": mine} if mine else None
    if res["mode"] == "platform" and res["platform"] != platform:
        return None
    if any(r["event"] in TARGET_DONE for r in rcpts):
        return None
    return res


def pending(root: Path, platform: str, include_held: bool = False) -> list[dict]:
    """An observer's queue. A message whose latest receipt is `held` (the observer is waiting on something, such as
    someone taking the orchestrator role) is left out unless asked for, so a watcher does not wake for it again."""
    state = registry(root)
    out = []
    for msg in all_messages(root):
        work = work_for(root, msg, platform, state)
        if work is None:
            continue
        rcpts = receipts(root, msg["id"])
        if rcpts and rcpts[-1]["event"] == "held" and not include_held:
            continue
        out.append({**msg, "work": work})
    return out


def unread(root: Path, reader: str) -> list[dict]:
    """Messages for `reader` (a platform, or one address) that its platform has not read. A message counts as for an
    address when it is addressed to it or resolves to it through a channel or role."""
    platform = platform_of(reader)
    state = registry(root)
    out = []
    for msg in all_messages(root):
        targets = [t["address"] for t in resolve(root, msg, state)["targets"]]
        if ":" not in reader:
            mine = msg["to"] == reader or any(platform_of(t) == reader for t in targets)
        else:
            mine = msg["to"] == reader or reader in targets
        if mine and not any(r["event"] in READER_DONE and platform_of(r["by"]) == platform
                            for r in receipts(root, msg["id"])):
            out.append(msg)
    return out


def hint(root: Path, msg: dict) -> dict:
    """For a message to a bare platform: the session the thread points at, if any. A reply goes back to whoever on
    that platform sent the message it answers; otherwise to whoever on it last wrote in the thread."""
    platform = msg["to"]
    if msg.get("in_reply_to"):
        try:
            parent = load_message(root, msg["in_reply_to"])
        except MailError:
            parent = None
        if parent and platform_of(parent["from"]) == platform:
            return {"address": parent["from"], "rule": "reply", "reason": f"it answers {parent['id']}"}
    earlier = [m for m in all_messages(root) if m["thread"] == msg["thread"] and m["id"] != msg["id"]]
    for m in reversed(earlier):
        if platform_of(m["from"]) == platform:
            return {"address": m["from"], "rule": "thread", "reason": f"last wrote in thread {msg['thread']}"}
    return {"address": None, "rule": "content", "reason": "nothing in the thread: read it and decide, or the fallback"}


# Presence: who is around and what they are doing, for observers placing unaddressed mail


def presence(root: Path) -> list[dict]:
    return sorted(read_folder(root / "presence"), key=lambda e: e.get("updated_at", ""), reverse=True)


def git_context() -> dict:
    ctx = {}
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    top = git("rev-parse", "--show-toplevel")
    if branch:
        ctx["branch"] = branch
    if top:
        ctx["worktree"] = top
    return ctx


# Output


def headline(msg: dict) -> str:
    reply = ", wants a reply" if msg.get("wants_reply") else ""
    return f"{msg['id']}  [{msg['project']}] {msg['kind']}{reply}  {msg['from']} -> {msg['to']}  {msg['subject']}"


def show(msg: dict, rcpts: list[dict] | None = None) -> str:
    lines = [
        f"Message {msg['id']} ({msg['kind']}{', wants a reply' if msg.get('wants_reply') else ''}), project {msg['project']}",
        f"From: {msg['from']}   To: {msg['to']}   Reply to: {msg['reply_to']}",
        f"Thread: {msg['thread']}" + (f"   In reply to: {msg['in_reply_to']}" if msg.get("in_reply_to") else ""),
        f"Sent: {msg['created_at']}",
        f"Subject: {msg['subject']}",
    ]
    if msg.get("context"):
        lines.append("Context: " + ", ".join(f"{k}={v}" for k, v in msg["context"].items()))
    lines += ["", msg["body"].rstrip()]
    if rcpts:
        lines += ["", "Receipts:"]
        for r in rcpts:
            extra = "  ".join(f"{k}={r[k]}" for k in ("target", "instead_of", "ref", "note") if r.get(k))
            lines.append(f"  {r['at']}  {r['event']:<9} by {r['by']}  {extra}".rstrip())
    return "\n".join(lines)


def envelope(msg: dict, why: str | None = None) -> str:
    """The text a Claude observer puts into a session with SendMessage: a self-contained first line, then everything
    the session needs to act without opening a file."""
    script = Path(__file__).resolve()
    want = "wants a reply" if msg.get("wants_reply") else "no reply needed"
    body = msg["body"].rstrip()
    if len(body) > ENVELOPE_BODY_LIMIT:
        body = body[:ENVELOPE_BODY_LIMIT] + f"\n\n[cut at {ENVELOPE_BODY_LIMIT} characters: read it all with `mail.py read`]"
    lines = [
        f"Agent mail from {msg['from']}: {msg['subject']} ({msg['kind']}, {want}).",
        "",
        f"Message {msg['id']}, project {msg['project']}, to {msg['to']}, thread {msg['thread']}"
        + (f", in reply to {msg['in_reply_to']}" if msg.get("in_reply_to") else "") + ".",
    ]
    if why:
        lines.append(f"You get it because {why}.")
    if msg.get("context"):
        lines.append("Context: " + ", ".join(f"{k}={v}" for k, v in msg["context"].items()) + ".")
    lines += ["", body, ""]
    if msg.get("wants_reply"):
        lines += ["Load the agent-mail skill to handle this. Mark it read and reply with:",
                  f"  python3 {script} read {msg['id']}",
                  f"  python3 {script} reply {msg['id']} --body-file <your answer>"]
    else:
        lines += ["Load the agent-mail skill if you need it. Mark it read with:",
                  f"  python3 {script} read {msg['id']}"]
    return "\n".join(lines)


def emit(data, as_json: bool, text: str) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False) if as_json else text)


def body_from(args) -> str:
    if args.body is not None:
        return args.body
    if args.body_file == "-":
        return sys.stdin.read()
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    raise MailError("give --body or --body-file (- for stdin)")


def parse_context(pairs: list[str] | None) -> dict:
    ctx = git_context()
    for pair in pairs or []:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise MailError(f"--context wants key=value, not {pair!r}")
        ctx[key] = value
    return ctx


def project_of(args) -> str:
    return check_name(args.project, "project") if getattr(args, "project", None) else my_project()


def subject_of(args) -> str:
    return check_address(args.as_address) if getattr(args, "as_address", None) else my_address()


# Commands


def cmd_whoami(args, root: Path) -> None:
    me = my_address()
    try:
        project = my_project()
    except MailError:
        project = None
    state = registry(root)
    channels = sorted(c for c, held in state["attached"].items() if me in held)
    roles = sorted(f"{p}/{r}" for (p, r), held in state["roles"].items() if me in held)
    data = {"address": me, "project": project, "mailbox": str(root), "channels": channels, "roles": roles}
    emit(data, args.json, f"{me}  project {project or '(none)'}\nmailbox: {root}"
         + (f"\nchannels: {', '.join(channels)}" if channels else "") + (f"\nroles: {', '.join(roles)}" if roles else ""))


def cmd_hello(args, root: Path) -> None:
    me = my_address()
    entry = {"address": me, "platform": platform_of(me), "project": project_of(args), "title": args.title or "",
             "topics": args.topics or "", "updated_at": iso(now()), **git_context()}
    write_json(root, root / "presence" / (me.replace(":", "__") + ".json"), entry)
    emit(entry, args.json, f"{me} is here: {entry['title'] or '(no title)'}")


def cmd_who(args, root: Path) -> None:
    entries = [e for e in presence(root) if not args.project or e.get("project") == args.project]
    text = "\n".join(
        f"{e['address']}  [{e.get('project', '')}] {e.get('title', '')}  ({e.get('branch', '')})  seen {e.get('updated_at', '')}"
        + (f"\n    topics: {e['topics']}" if e.get("topics") else "")
        for e in entries
    ) or "nobody has said hello"
    emit(entries, args.json, text)


def cmd_channel(args, root: Path) -> None:
    state = registry(root)
    if args.action == "list":
        rows = [c for c in state["channels"].values() if not args.project or c["project"] == args.project]
        lines = [f"{c['name']}  [{c['project']}]  {len(state['attached'].get(c['name'], {}))} attached  "
                 f"{c.get('qualifiers') or ''}".rstrip() for c in sorted(rows, key=lambda c: c["name"])]
        emit(rows, args.json, "\n".join(lines) or "no channels")
        return
    name = check_name(args.name or "", "channel")
    if args.action == "create":
        project = project_of(args)
        existing = state["channels"].get(name)
        if existing and existing["project"] != project:
            raise MailError(f"channel {name} already belongs to project {existing['project']}")
        if not args.purpose:
            raise MailError("a channel needs --purpose: why it exists, in a sentence")
        event = record(root, "create", "channel", name, project, qualifiers=args.purpose)
        emit(event, args.json, f"channel {name} ({project}) {'updated' if existing else 'created'}")
        return
    channel = state["channels"].get(name)
    if not channel:
        raise MailError(f"no channel {name}")
    attached = list(state["attached"].get(name, {}).values())
    lines = [f"channel {name}  [{channel['project']}]  {channel.get('qualifiers') or ''}".rstrip()]
    lines += [f"  {a['address']}  {a.get('qualifiers') or ''}".rstrip() for a in attached] or ["  nobody attached"]
    emit({"channel": channel, "attached": attached}, args.json, "\n".join(lines))


def cmd_attach(args, root: Path) -> None:
    channel = registry(root)["channels"].get(args.channel)
    if not channel:
        raise MailError(f"no channel {args.channel}: create it first (mail.py channel create)")
    who = subject_of(args)
    replaces = check_address(args.replace) if args.replace else None
    event = record(root, "attach", "channel", args.channel, channel["project"], address=who,
                   qualifiers=args.qualifiers, replaces=replaces)
    emit(event, args.json, f"{who} attached to {args.channel}" + (f" in place of {replaces}" if replaces else ""))


def cmd_detach(args, root: Path) -> None:
    channel = registry(root)["channels"].get(args.channel)
    if not channel:
        raise MailError(f"no channel {args.channel}")
    who = subject_of(args)
    event = record(root, "detach", "channel", args.channel, channel["project"], address=who)
    emit(event, args.json, f"{who} detached from {args.channel}")


def cmd_role(args, root: Path) -> None:
    project = project_of(args)
    if args.action == "list":
        state = registry(root)
        rows = [{"project": p, "role": r, "holders": list(h.values())} for (p, r), h in sorted(state["roles"].items())
                if h and (args.all or p == project)]
        lines = []
        for row in rows:
            lines.append(f"{row['project']}/{row['role']}")
            lines += [f"  {h['address']}  {h.get('qualifiers') or ''}".rstrip() for h in row["holders"]]
        emit(rows, args.json, "\n".join(lines) or f"no roles held in {project}")
        return
    name = check_name(args.name or "", "role")
    who = subject_of(args)
    if args.action == "claim":
        replaces = check_address(args.replace) if args.replace else None
        event = record(root, "claim", "role", name, project, address=who, qualifiers=args.qualifiers, replaces=replaces)
        emit(event, args.json, f"{who} holds {project}/{name}" + (f" in place of {replaces}" if replaces else ""))
    else:
        event = record(root, "release", "role", name, project, address=who)
        emit(event, args.json, f"{who} released {project}/{name}")


def cmd_send(args, root: Path) -> None:
    msg = make_message(my_address(), args.to, args.kind, args.subject, body_from(args), project=project_of(args),
                       thread=args.thread, in_reply_to=args.in_reply_to, reply_to=args.reply_to,
                       context=parse_context(args.context), wants_reply=args.wants_reply)
    post(root, msg)
    emit(msg, args.json, msg["id"])


def cmd_reply(args, root: Path) -> None:
    me = my_address()
    original = load_message(root, args.id)
    msg = make_message(me, original["reply_to"], args.kind, args.subject or f"Re: {original['subject']}",
                       body_from(args), project=original["project"], thread=original["thread"],
                       in_reply_to=original["id"], reply_to=args.reply_to, context=parse_context(args.context),
                       wants_reply=args.wants_reply)
    post(root, msg)
    if msg["kind"] == "reply":  # a tell in the thread (who owns it now, it could not be delivered) answers nothing
        add_receipt(root, original["id"], "answered", me, ref=msg["id"])
    emit(msg, args.json, msg["id"])


def cmd_read(args, root: Path) -> None:
    msg = load_message(root, args.id)
    if not args.peek:
        add_receipt(root, msg["id"], "read", my_address())
    emit(msg, args.json, show(msg))


def cmd_status(args, root: Path) -> None:
    msg = load_message(root, args.id)
    rcpts = receipts(root, msg["id"])
    emit({"message": msg, "receipts": rcpts, "resolved": resolve(root, msg)}, args.json, show(msg, rcpts))


def cmd_thread(args, root: Path) -> None:
    first = load_message(root, args.id)
    msgs = [m for m in all_messages(root) if m["thread"] == first["thread"]]
    emit(msgs, args.json, "\n\n----\n\n".join(show(m, receipts(root, m["id"])) for m in msgs))


def cmd_inbox(args, root: Path) -> None:
    reader = args.reader or my_address()
    if reader not in PLATFORMS:
        check_address(reader)
    msgs = unread(root, reader)
    emit(msgs, args.json, "\n".join(headline(m) for m in msgs) or "no unread mail")


def cmd_pending(args, root: Path) -> None:
    msgs = pending(root, args.platform, include_held=args.include_held)
    emit(msgs, args.json, "\n".join(headline(m) for m in msgs) or "nothing waiting")


def cmd_targets(args, root: Path) -> None:
    msg = load_message(root, args.id)
    state = registry(root)
    work = work_for(root, msg, args.platform, state)
    if work is None:
        emit({"mode": "done", "targets": []}, args.json, f"nothing left for {args.platform}")
        return
    if work["mode"] == "platform":
        work["hint"] = hint(root, msg)
        work["fallback"] = list(role_holders(state, msg["project"], FALLBACK_ROLE))
    lines = [f"mode {work['mode']}"]
    for t in work["targets"]:
        lines.append(f"  {t['address']}  rule={t['rule']}  via {t['via']}"
                     + (f"  replaces {t['replaces']}" if t.get("replaces") else "")
                     + (f"\n      qualifiers: {t['qualifiers']}" if t.get("qualifiers") else ""))
    if work.get("hint"):
        h = work["hint"]
        lines.append(f"  hint: {h['address'] or '(decide)'}  rule={h['rule']}  {h['reason']}")
        lines.append(f"  fallback (role:{FALLBACK_ROLE}): {', '.join(work['fallback']) or 'nobody'}")
    if work.get("reason"):
        lines.append(f"  {work['reason']}")
    emit(work, args.json, "\n".join(lines))


def cmd_envelope(args, root: Path) -> None:
    msg = load_message(root, args.id)
    why = args.why
    if not why and args.target:
        for t in resolve(root, msg)["targets"]:
            if t["address"] == args.target and t["via"] != t["address"]:
                why = f"you are attached to {t['via']}" if t["via"].startswith("channel:") else f"you hold {t['via']}"
                if t["rule"] == "fallback":
                    why += f" and nobody holds {msg['to']}"
                if t.get("replaces"):
                    why += f", in place of {t['replaces']}"
                if t.get("qualifiers"):
                    why += f" (your note: {t['qualifiers']})"
    print(envelope(msg, why))


def cmd_mark(args, root: Path) -> None:
    load_message(root, args.id)
    receipt = add_receipt(root, args.id, args.event, my_address(),
                          target=check_address(args.target) if args.target else None,
                          instead_of=check_address(args.instead_of) if args.instead_of else None,
                          ref=args.ref, note=args.note)
    emit(receipt, args.json, f"{args.id}: {args.event}")


def cmd_watch(args, root: Path) -> None:
    """--once: exit as soon as the platform's queue is not empty (made for a background command that wakes its session
    when it exits). --follow: print each newly waiting message, forever (made for a monitor)."""
    seen: set[str] = set()
    deadline = time.monotonic() + args.timeout if args.timeout else None
    while True:
        waiting = pending(root, args.platform)
        if args.once and waiting:
            for m in waiting:
                print(headline(m), flush=True)
            return
        if not args.once:
            for m in waiting:
                if m["id"] not in seen:
                    seen.add(m["id"])
                    print(headline(m), flush=True)
        if deadline and time.monotonic() >= deadline:
            print("watch timed out with nothing waiting", flush=True)
            return
        time.sleep(args.interval)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mail.py", description="Agent mail between Claude and Codex sessions.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print JSON instead of text")
    sub = p.add_subparsers(dest="command", required=True)

    def command(name: str, **kw) -> argparse.ArgumentParser:
        return sub.add_parser(name, parents=[common], **kw)  # --json on every command

    def project_arg(s):
        s.add_argument("--project", help="the project (default: $AGENT_MAIL_PROJECT, or the main checkout's folder name)")

    def handover_args(s):
        s.add_argument("--as", dest="as_address", help="register another session (handing over a channel or role)")
        s.add_argument("--replace", help="the address this takes over from: its undelivered mail comes here")

    command("whoami", help="your address, project, channels and roles").set_defaults(fn=cmd_whoami)

    s = command("hello", help="say you are here and what you are doing (for placing unaddressed mail)")
    s.add_argument("--title")
    s.add_argument("--topics", help="a line of what you are working on")
    project_arg(s)
    s.set_defaults(fn=cmd_hello)

    s = command("who", help="who has said hello, newest first")
    s.add_argument("--project")
    s.set_defaults(fn=cmd_who)

    s = command("channel", help="create, list or show channels")
    s.add_argument("action", choices=("create", "list", "show"))
    s.add_argument("name", nargs="?")
    s.add_argument("--purpose", help="create: why the channel exists, in a sentence")
    project_arg(s)
    s.set_defaults(fn=cmd_channel)

    s = command("attach", help="listen to a channel")
    s.add_argument("channel")
    s.add_argument("--qualifiers", help="why you are attached: what you handle from this channel")
    handover_args(s)
    s.set_defaults(fn=cmd_attach)

    s = command("detach", help="stop listening to a channel")
    s.add_argument("channel")
    s.add_argument("--as", dest="as_address", help="detach another session")
    s.set_defaults(fn=cmd_detach)

    s = command("role", help="claim, release or list roles in a project")
    s.add_argument("action", choices=("claim", "release", "list"))
    s.add_argument("name", nargs="?")
    s.add_argument("--qualifiers", help="claim: what you do in this role")
    s.add_argument("--all", action="store_true", help="list: every project")
    project_arg(s)
    handover_args(s)
    s.set_defaults(fn=cmd_role)

    def body_args(s):
        s.add_argument("--body")
        s.add_argument("--body-file", help="a file with the body, or - for stdin")
        s.add_argument("--context", action="append", metavar="KEY=VALUE", help="extra context (repeatable)")
        s.add_argument("--reply-to", help="where answers go, if not to you: an address, role:<name> or channel:<id>")
        g = s.add_mutually_exclusive_group()
        g.add_argument("--wants-reply", dest="wants_reply", action="store_true", default=None)
        g.add_argument("--no-reply", dest="wants_reply", action="store_false")

    s = command("send", help="post a message")
    s.add_argument("--to", required=True, help="claude, codex, <platform>:<session>, role:<name> or channel:<id>")
    s.add_argument("--kind", choices=KINDS, default="ask")
    s.add_argument("--subject", required=True)
    s.add_argument("--thread")
    s.add_argument("--in-reply-to")
    project_arg(s)
    body_args(s)
    s.set_defaults(fn=cmd_send)

    s = command("reply", help="answer a message: goes to its reply_to, in its thread and project")
    s.add_argument("id")
    s.add_argument("--kind", choices=KINDS, default="reply")
    s.add_argument("--subject")
    body_args(s)
    s.set_defaults(fn=cmd_reply)

    s = command("read", help="show a message and record that you read it")
    s.add_argument("id")
    s.add_argument("--peek", action="store_true", help="do not record a read receipt")
    s.set_defaults(fn=cmd_read)

    s = command("status", help="a message, its receipts and who it resolves to")
    s.add_argument("id")
    s.set_defaults(fn=cmd_status)

    s = command("thread", help="every message in a message's thread")
    s.add_argument("id")
    s.set_defaults(fn=cmd_thread)

    s = command("inbox", help="unread mail for you (or --for an address or platform)")
    s.add_argument("--for", dest="reader")
    s.set_defaults(fn=cmd_inbox)

    s = command("pending", help="a platform observer's queue")
    s.add_argument("--for", dest="platform", choices=PLATFORMS, required=True)
    s.add_argument("--include-held", action="store_true", help="also show messages being held")
    s.set_defaults(fn=cmd_pending)

    s = command("targets", help="what a platform's observer still has to deliver for a message, and to whom")
    s.add_argument("id")
    s.add_argument("--for", dest="platform", choices=PLATFORMS, required=True)
    s.set_defaults(fn=cmd_targets)

    s = command("envelope", help="the text a Claude observer delivers into a session")
    s.add_argument("id")
    s.add_argument("--target", help="the session it goes to, so the text can say why it gets it")
    s.add_argument("--why", help="say why yourself instead")
    s.set_defaults(fn=cmd_envelope)

    s = command("mark", help="record a receipt")
    s.add_argument("id")
    s.add_argument("event", choices=EVENTS)
    s.add_argument("--target", help="the address it was routed, delivered or delegated to")
    s.add_argument("--instead-of", help="delivered: the target this delivery stands in for (it could not take it)")
    s.add_argument("--ref", help="a related message id")
    s.add_argument("--note", help="why")
    s.set_defaults(fn=cmd_mark)

    s = command("watch", help="wait for a platform observer's queue")
    s.add_argument("--for", dest="platform", choices=PLATFORMS, required=True)
    mode = s.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--follow", action="store_true")
    s.add_argument("--interval", type=float, default=2.0, help="seconds between looks (default 2)")
    s.add_argument("--timeout", type=float, default=0, help="give up after this many seconds (default never)")
    s.set_defaults(fn=cmd_watch)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.fn(args, mail_root())
    except MailError as e:
        print(f"mail.py: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
