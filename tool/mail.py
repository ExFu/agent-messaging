#!/usr/bin/env python3
"""Agent mail: one mailbox on this Mac for Claude and Codex sessions (docs/contract-v1.md, schema agent-mail/2).

First slice, manual mode. Each agent reads its own mail with this command and marks what it did. There is no relay,
no automatic wake-up and no lease yet: a human (or the agent itself) decides when to look.

    M=tool/mail.py
    python3 $M whoami
    python3 $M project create demo --escalation claude
    python3 $M session register --project demo --title "Unlock screen" [--identity-evidence "..."]
    python3 $M channel create demo.unlock --purpose "The unlock screen rebuild"
    python3 $M attach demo.unlock --qualifier "copy and layout only"
    python3 $M catch-up demo.unlock --from pending          # or --from <message id>
    python3 $M send --to channel:demo.unlock --platform codex --kind ask --subject "..." --body-file q.md
    python3 $M inbox                                        # my open mail
    python3 $M read <id>                                    # print it and mark it read
    python3 $M reply <id> --body-file answer.md             # reply, and mark the original answered
    python3 $M mark <id> closed --note "done"               # or progress / skipped
    python3 $M thread <id>    python3 $M status <id>    python3 $M channels    python3 $M sessions

Your address comes from --as, else $AGENT_MAIL_FROM, else claude:$CLAUDE_CODE_HOST_SESSION_ID, else
codex:$CODEX_THREAD_ID. The mailbox is ~/.agent-mail/, or $AGENT_MAIL_DIR for tests. Add --json to any command for
machine-readable output. Stdlib only, Python 3.9 or newer, local disk only.

Supported in this slice: project, mandate, session, session-end, channel, attach (with qualifier and --updates),
detach, catch-up, send, reply, read, mark (read, progress, answered, skipped, closed), inbox, thread, status.
In manual mode every candidate counts as chosen until it marks itself `skipped`.

For a platform's relay (Claude's router; contract section 9):

    python3 $M lease acquire --platform claude --seconds 600   # prints the generation; renew the same way
    python3 $M pending --for claude                             # what the relay should do next
    python3 $M watch --for claude --timeout 3600                # exits 0 when there is work, 1 on timeout
    python3 $M envelope <id> --for <address>                    # the text to deliver
    python3 $M relay <id> <recipient> routed --lease <gen> --note "why"
    python3 $M relay <id> <recipient> attempt-started --lease <gen>     # prints attempt_id; then send
    python3 $M relay <id> <recipient> delivered --lease <gen> --attempt-id <aid>

A recipient that has already marked a message itself is never in the relay's queue: it is handling it by hand.

Not yet supported (refused, never faked): roles, replace, reroute, retry records, presence, relay config records,
escalation notices.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import json
import os
import re
import secrets
import sys
from pathlib import Path

SCHEMA = "agent-mail/2"
PLATFORMS = ("claude", "codex")
KINDS = ("ask", "request", "tell", "reply")
WANTS_REPLY = {"ask": True, "request": True, "tell": False, "reply": False}
RECIPIENT_MARKS = ("read", "progress", "answered", "skipped", "closed")
# A recipient's obligation is over once it records one of these.
FINISHED = ("closed", "skipped", "transferred")
REGISTRY_RECORDS = ("project", "mandate", "mandate-revoke", "session", "session-end", "channel", "attach", "detach",
                    "catch-up")
FOLDERS = ("registry", "messages", "receipts")
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
ADDRESS = re.compile(r"^(claude|codex):[A-Za-z0-9._-]{1,128}$")


class MailError(Exception):
    pass


# Mailbox, identity and time


def mailbox() -> Path:
    return Path(os.environ.get("AGENT_MAIL_DIR") or Path.home() / ".agent-mail").expanduser()


def whoami(explicit: str | None = None) -> str:
    if explicit:
        address = explicit
    elif os.environ.get("AGENT_MAIL_FROM"):
        address = os.environ["AGENT_MAIL_FROM"]
    elif os.environ.get("CLAUDE_CODE_HOST_SESSION_ID"):
        address = "claude:" + os.environ["CLAUDE_CODE_HOST_SESSION_ID"]
    elif os.environ.get("CODEX_THREAD_ID"):
        address = "codex:" + os.environ["CODEX_THREAD_ID"]
    else:
        raise MailError("cannot tell who you are: pass --as, or set AGENT_MAIL_FROM")
    if not ADDRESS.match(address):
        raise MailError(f"not an address: {address!r} (want claude:<id> or codex:<id>)")
    return address


def platform_of(address: str) -> str:
    return address.split(":", 1)[0]


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def new_id(address: str, t: dt.datetime) -> str:
    stamp = t.strftime("%Y%m%dT%H%M%S.") + f"{t.microsecond // 1000:03d}Z"
    return f"{stamp}-{platform_of(address)}-{secrets.token_hex(4)}"


# Storage: lock, recovery, publication (contract section 4)


def ensure_layout(root: Path) -> None:
    for sub in FOLDERS + ("tmp", "leases"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "lock").touch(exist_ok=True)


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def published_seq(name: str) -> int:
    return int(name.split("-", 1)[0])


def highest_published(root: Path) -> int:
    top = 0
    for folder in FOLDERS:
        for entry in os.scandir(root / folder):
            if entry.name.endswith(".json"):
                top = max(top, published_seq(entry.name))
    return top


def read_seq_file(root: Path) -> int:
    try:
        return int((root / "seq").read_text().strip() or 0)
    except FileNotFoundError:
        return 0


def write_seq_file(root: Path, value: int) -> None:
    tmp = root / "tmp" / "seq.tmp"
    with open(tmp, "w") as f:
        f.write(f"{value}\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, root / "seq")
    fsync_dir(root)


def published_by_seq(root: Path, seq: int) -> Path | None:
    prefix = f"{seq:012d}-"
    for folder in FOLDERS:
        for entry in os.scandir(root / folder):
            if entry.name.startswith(prefix):
                return Path(entry.path)
    return None


def needs_recovery(root: Path) -> bool:
    return any(os.scandir(root / "tmp")) or read_seq_file(root) != highest_published(root)


def recover(root: Path) -> None:
    """Under the exclusive lock: finish or discard what a crashed writer left (contract section 4)."""
    for entry in list(os.scandir(root / "tmp")):
        path = Path(entry.path)
        if entry.name.endswith(".tmp") and entry.name[:-4].isdigit():
            done = published_by_seq(root, int(entry.name[:-4]))
            if done is not None:
                fsync_dir(done.parent)
        path.unlink()
    top = highest_published(root)
    if read_seq_file(root) != top:
        write_seq_file(root, top)


@contextlib.contextmanager
def locked(root: Path, exclusive: bool):
    ensure_layout(root)
    with open(root / "lock", "r+") as lock:
        if exclusive:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if needs_recovery(root):
                recover(root)
        else:
            fcntl.flock(lock, fcntl.LOCK_SH)
            if needs_recovery(root):
                fcntl.flock(lock, fcntl.LOCK_UN)
                fcntl.flock(lock, fcntl.LOCK_EX)
                if needs_recovery(root):
                    recover(root)
                fcntl.flock(lock, fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def load_all(root: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for folder in FOLDERS:
        records = []
        for entry in sorted(os.scandir(root / folder), key=lambda e: e.name):
            if entry.name.endswith(".json"):
                with open(entry.path) as f:
                    record = json.load(f)
                if record.get("schema") != SCHEMA:
                    raise MailError(f"unknown schema in {entry.path}: {record.get('schema')!r}")
                records.append(record)
        out[folder] = records
    return out


def publish(root: Path, folder: str, record: dict, state: dict[str, list[dict]]) -> dict:
    """Assign seq and publish one record. Caller holds the exclusive lock and passes a fresh `state`."""
    for f in FOLDERS:
        if any(r["id"] == record["id"] for r in state[f]):
            raise MailError(f"id already published: {record['id']}")
    seq = read_seq_file(root) + 1
    record["seq"] = seq
    if folder == "messages":
        record["registry_revision"] = max((r["seq"] for r in state["registry"]), default=0)
    tmp = root / "tmp" / f"{seq}.tmp"
    with open(tmp, "w") as f:
        json.dump(record, f, indent=1, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    dest = root / folder / f"{seq:012d}-{record['id']}.json"
    os.link(tmp, dest)
    fsync_dir(dest.parent)
    tmp.unlink()
    write_seq_file(root, seq)
    state[folder].append(record)
    return record


def base_record(address: str, project: str) -> dict:
    t = now()
    return {"schema": SCHEMA, "id": new_id(address, t), "seq": None, "project": project, "by": address,
            "time": iso(t)}


# The registry folded at a point in time


class Registry:
    """Registry state built from records with seq below `upto` (all records when None)."""

    def __init__(self, records: list[dict], upto: int | None = None):
        self.projects: dict[str, dict] = {}
        self.sessions: dict[tuple[str, str], dict] = {}  # (project, address) -> session record
        self.ended: set[tuple[str, str]] = set()
        self.channels: dict[str, dict] = {}
        self.attachments: dict[tuple[str, str], dict] = {}  # (channel, address) -> attach record
        self.mandates: dict[str, dict] = {}
        for r in records:
            if upto is not None and r["seq"] >= upto:
                break
            kind = r["record"]
            if kind == "project":
                self.projects[r["name"]] = r
            elif kind == "mandate":
                self.mandates[r["id"]] = r
            elif kind == "mandate-revoke":
                self.mandates.pop(r["mandate"], None)
            elif kind == "session":
                self.sessions[(r["project"], r["address"])] = r
                self.ended.discard((r["project"], r["address"]))
            elif kind == "session-end":
                self.ended.add((r["project"], r["address"]))
            elif kind == "channel":
                self.channels[r["channel"]] = r
            elif kind == "attach":
                self.attachments[(r["channel"], r["address"])] = r
            elif kind == "detach":
                self.attachments.pop((r["channel"], r["address"]), None)

    def listeners(self, channel: str) -> list[dict]:
        return [a for (c, _), a in self.attachments.items() if c == channel]


# Who a message is for (contract section 7, manual mode)


def candidates(msg: dict, state: dict[str, list[dict]], with_catch_ups: bool = True) -> dict[str, dict]:
    """Address -> {"via", "qualifier", "how"} for everyone the message is for, from its snapshot plus catch-ups."""
    target, project, platform = msg["to"], msg["project"], msg.get("platform")
    snapshot = Registry(state["registry"], upto=msg["seq"])
    out: dict[str, dict] = {}
    if not with_catch_ups and target.startswith("channel:"):
        for a in snapshot.listeners(target[len("channel:"):]):
            if platform in (None, platform_of(a["address"])):
                out[a["address"]] = {"via": target, "qualifier": a.get("qualifier"), "how": "attached"}
        out.pop(msg["from"], None)
        return out
    if ADDRESS.match(target):
        out[target] = {"via": target, "qualifier": None, "how": "addressed directly"}
    elif target.startswith("channel:"):
        channel = target[len("channel:"):]
        for a in snapshot.listeners(channel):
            if platform in (None, platform_of(a["address"])):
                out[a["address"]] = {"via": target, "qualifier": a.get("qualifier"), "how": "attached"}
        for c in state["registry"]:
            if c["record"] != "catch-up" or c["scope"] != target or c["seq"] < msg["seq"]:
                continue
            if platform not in (None, platform_of(c["address"])) or c["address"] in out:
                continue
            if catch_up_covers(c, msg, state):
                live = Registry(state["registry"], upto=c["seq"] + 1)
                attach = live.attachments.get((channel, c["address"]))
                out[c["address"]] = {"via": target, "qualifier": attach.get("qualifier") if attach else None,
                                     "how": f"catch-up {c['id']}"}
    elif target in PLATFORMS:
        for (p, address) in snapshot.sessions:
            if p == project and platform_of(address) == target:
                out[address] = {"via": target, "qualifier": None, "how": "bare platform"}
    else:
        raise MailError(f"target not supported in this slice: {target!r}")
    out.pop(msg["from"], None)
    return out


def catch_up_covers(c: dict, msg: dict, state: dict[str, list[dict]]) -> bool:
    if c["from"] == "pending":
        # Pending: nobody was listening when it was sent, or someone it was for has not finished it yet.
        original = candidates(msg, state, with_catch_ups=False)
        return not original or any(not any(m in FINISHED for m in my_marks(msg["id"], a, state)) for a in original)
    start = next((m for m in state["messages"] if m["id"] == c["from"]), None)
    return start is not None and start["seq"] <= msg["seq"]


def my_marks(msg_id: str, address: str, state: dict[str, list[dict]]) -> list[str]:
    """The recipient's own marks (plus `transferred`), not the relay's routing and delivery receipts."""
    return [r["disposition"] for r in state["receipts"] if r["message"] == msg_id and r.get("recipient") == address
            and r["disposition"] in RECIPIENT_MARKS + ("transferred",)]


def find_message(msg_id: str, state: dict[str, list[dict]]) -> dict:
    for m in state["messages"]:
        if m["id"] == msg_id:
            return m
    raise MailError(f"no such message: {msg_id}")


# Commands


def cmd_whoami(args, root):
    address = whoami(args.as_)
    with locked(root, exclusive=False):
        reg = Registry(load_all(root)["registry"])
    projects = sorted(p for (p, a) in reg.sessions if a == address and (p, a) not in reg.ended)
    return {"address": address, "platform": platform_of(address), "registered_in": projects, "mailbox": str(root)}


def write_registry(root, address: str, project: str, record: str, fields: dict, check=None) -> dict:
    with locked(root, exclusive=True):
        state = load_all(root)
        reg = Registry(state["registry"])
        if record != "project" and project not in reg.projects:
            raise MailError(f"no such project: {project} (create it with: project create {project})")
        if check:
            check(reg)
        r = base_record(address, project)
        r["record"] = record
        r.update(fields)
        return publish(root, "registry", r, state)


def cmd_project_create(args, root):
    if not NAME.match(args.name):
        raise MailError(f"bad project name: {args.name!r}")

    def check(reg):
        if args.name in reg.projects:
            raise MailError(f"project already exists: {args.name}")
    return write_registry(root, whoami(args.as_), args.name, "project",
                          {"name": args.name, "escalation": args.escalation}, check)


def cmd_mandate_add(args, root):
    scope = {"channels": args.channel or [], "recipients": args.recipient or [], "actions": args.action or []}
    return write_registry(root, whoami(args.as_), args.project, "mandate",
                          {"quote": args.quote, "said_at": args.said_at, "source": args.source, "scope": scope})


def cmd_mandates(args, root):
    with locked(root, exclusive=False):
        reg = Registry(load_all(root)["registry"])
    return [{k: m[k] for k in ("id", "project", "by", "quote", "said_at", "source", "scope")}
            for m in reg.mandates.values() if not args.project or m["project"] == args.project]


def cmd_session_register(args, root):
    address = whoami(args.as_)

    def check(reg):
        if args.mandate and args.mandate not in reg.mandates:
            raise MailError(f"no such mandate in force: {args.mandate}")
    fields = {"address": address, "title": args.title, "worktree": args.worktree or os.getcwd(),
              "identity_evidence": args.identity_evidence, "mandate": args.mandate}
    if args.host_id:
        fields["host_id"] = args.host_id
    return write_registry(root, address, args.project, "session", fields, check)


def cmd_session_end(args, root):
    return write_registry(root, whoami(args.as_), args.project, "session-end",
                          {"address": args.address, "reason": args.reason, "evidence": args.evidence})


def channel_project(channel: str) -> str:
    if not NAME.match(channel) or "." not in channel:
        raise MailError(f"bad channel id: {channel!r} (want <project>.<name>)")
    return channel.split(".", 1)[0]


def cmd_channel_create(args, root):
    project = args.project or channel_project(args.channel)

    def check(reg):
        if args.channel in reg.channels:
            raise MailError(f"channel already exists: {args.channel}")
    return write_registry(root, whoami(args.as_), project, "channel",
                          {"channel": args.channel, "purpose": args.purpose}, check)


def require_channel(reg: Registry, channel: str) -> dict:
    if channel not in reg.channels:
        raise MailError(f"no such channel: {channel}")
    return reg.channels[channel]


def require_session(reg: Registry, project: str, address: str) -> None:
    if (project, address) not in reg.sessions or (project, address) in reg.ended:
        raise MailError(f"{address} is not registered in {project}: run session register first")


def cmd_attach(args, root):
    address = whoami(args.as_)
    with locked(root, exclusive=True):
        state = load_all(root)
        reg = Registry(state["registry"])
        ch = require_channel(reg, args.channel)
        require_session(reg, ch["project"], address)
        current = reg.attachments.get((args.channel, address))
        if args.updates:
            if not current or current["id"] != args.updates:
                raise MailError(f"--updates must name your current attachment to {args.channel}")
        elif current:
            raise MailError(f"already attached (id {current['id']}); pass --updates {current['id']} to change it")
        r = base_record(address, ch["project"])
        r.update({"record": "attach", "channel": args.channel, "address": address, "qualifier": args.qualifier})
        if args.updates:
            r["updates"] = args.updates
        return publish(root, "registry", r, state)


def cmd_detach(args, root):
    address = whoami(args.as_)
    with locked(root, exclusive=True):
        state = load_all(root)
        reg = Registry(state["registry"])
        ch = require_channel(reg, args.channel)
        if (args.channel, address) not in reg.attachments:
            raise MailError(f"not attached to {args.channel}")
        r = base_record(address, ch["project"])
        r.update({"record": "detach", "channel": args.channel, "address": address})
        return publish(root, "registry", r, state)


def cmd_catch_up(args, root):
    address = whoami(args.as_)
    with locked(root, exclusive=True):
        state = load_all(root)
        reg = Registry(state["registry"])
        ch = require_channel(reg, args.channel)
        require_session(reg, ch["project"], address)
        if args.from_ != "pending":
            start = find_message(args.from_, state)
            if start["to"] != f"channel:{args.channel}":
                raise MailError(f"{args.from_} was not sent to channel:{args.channel}")
        r = base_record(address, ch["project"])
        r.update({"record": "catch-up", "address": address, "scope": f"channel:{args.channel}", "from": args.from_})
        r = publish(root, "registry", r, state)
        how = f"catch-up {r['id']}"
        caught = sum(1 for m in state["messages"] if candidates(m, state).get(address, {}).get("how") == how)
        return {**r, "caught_up": caught}


def read_body(args) -> str:
    if args.body is not None:
        return args.body
    if args.body_file == "-":
        return sys.stdin.read()
    if args.body_file:
        return Path(args.body_file).read_text()
    raise MailError("give --body or --body-file (use - for stdin)")


def send_message(root, address: str, fields: dict, after=None) -> dict:
    with locked(root, exclusive=True):
        state = load_all(root)
        reg = Registry(state["registry"])
        to = fields["to"]
        if to.startswith("channel:"):
            ch = require_channel(reg, to[len("channel:"):])
            if fields.get("project") and fields["project"] != ch["project"]:
                raise MailError(f"project {fields['project']} does not match channel project {ch['project']}")
            fields["project"] = ch["project"]
        elif to.startswith("role:"):
            raise MailError("roles are not supported in this slice")
        elif not (ADDRESS.match(to) or to in PLATFORMS):
            raise MailError(f"bad target: {to!r}")
        project = fields.get("project")
        if not project:
            raise MailError("give --project for a message not sent to a channel")
        require_session(reg, project, address)
        if fields.get("platform") not in (None, *PLATFORMS):
            raise MailError(f"bad platform: {fields['platform']!r}")
        if fields.get("reply_platform") not in (None, "any", *PLATFORMS):
            raise MailError(f"bad reply platform: {fields['reply_platform']!r}")
        msg = base_record(address, project)
        msg.update({"registry_revision": None, "from": address, **fields})
        msg.setdefault("thread", msg["id"])
        msg = publish(root, "messages", msg, state)
        if after:
            after(state, msg)
        return msg


def cmd_send(args, root):
    address = whoami(args.as_)
    kind = args.kind
    fields = {"to": args.to, "project": args.project, "platform": args.platform, "reply_to": args.reply_to,
              "reply_platform": args.reply_platform or platform_of(address), "kind": kind,
              "wants_reply": WANTS_REPLY[kind] if args.wants_reply is None else args.wants_reply,
              "subject": args.subject, "body": read_body(args), "in_reply_to": None,
              "context": {"branch": args.branch, "files": args.file or [], "plan": args.plan}, "about": None}
    return send_message(root, address, fields)


def cmd_reply(args, root):
    address = whoami(args.as_)
    with locked(root, exclusive=False):
        original = find_message(args.id, load_all(root))
    to = args.to or original.get("reply_to") or original["from"]
    if args.platform is not None:
        platform = None if args.platform == "any" else args.platform
    elif ADDRESS.match(to):
        platform = None
    else:
        rp = original.get("reply_platform") or platform_of(original["from"])
        platform = None if rp == "any" else rp
    fields = {"to": to, "project": original["project"], "platform": platform, "reply_to": args.reply_to,
              "reply_platform": args.reply_platform or platform_of(address), "kind": "reply",
              "wants_reply": bool(args.wants_reply), "subject": args.subject or "Re: " + original["subject"],
              "body": read_body(args), "thread": original["thread"], "in_reply_to": original["id"],
              "context": {"branch": None, "files": [], "plan": None}, "about": None}

    def mark_answered(state, msg):
        finished = any(m in FINISHED for m in my_marks(original["id"], address, state))
        if address in candidates(original, state) and not finished:
            write_receipt(root, state, original, address, "answered", args.note or "replied", ref=msg["id"])
    return send_message(root, address, fields, after=mark_answered)


def write_receipt(root, state, msg: dict, address: str, disposition: str, note: str | None, ref=None) -> dict:
    marks = my_marks(msg["id"], address, state)
    if "transferred" in marks:
        raise MailError("this obligation was transferred to another session: stop acting on it")
    if any(m in ("closed", "skipped") for m in marks):
        raise MailError(f"already finished for you ({', '.join(marks)})")
    r = base_record(address, msg["project"])
    r.update({"message": msg["id"], "recipient": address, "disposition": disposition, "note": note, "ref": ref,
              "registry_revision": max((x["seq"] for x in state["registry"]), default=0)})
    return publish(root, "receipts", r, state)


def cmd_mark(args, root):
    address = whoami(args.as_)
    if args.disposition not in RECIPIENT_MARKS:
        raise MailError(f"in manual mode you can mark: {', '.join(RECIPIENT_MARKS)}")
    with locked(root, exclusive=True):
        state = load_all(root)
        msg = find_message(args.id, state)
        if address not in candidates(msg, state):
            raise MailError(f"{args.id} is not addressed to {address}")
        return write_receipt(root, state, msg, address, args.disposition, args.note, ref=args.ref)


def cmd_read(args, root):
    address = whoami(args.as_)
    with locked(root, exclusive=True):
        state = load_all(root)
        msg = find_message(args.id, state)
        cands = candidates(msg, state)
        mine = address in cands
        before = my_marks(msg["id"], address, state)
        if mine and not args.no_mark and not before:
            write_receipt(root, state, msg, address, "read", args.note)
        return {"message": msg, "for_you": cands.get(address), "earlier_marks": before,
                "your_marks": my_marks(msg["id"], address, state)}


def cmd_inbox(args, root):
    address = whoami(args.as_)
    with locked(root, exclusive=False):
        state = load_all(root)
    rows = []
    for msg in state["messages"]:
        cands = candidates(msg, state)
        if address not in cands:
            continue
        marks = my_marks(msg["id"], address, state)
        if not args.all and any(m in FINISHED for m in marks):
            continue
        rows.append({"id": msg["id"], "time": msg["time"], "from": msg["from"], "to": msg["to"],
                     "kind": msg["kind"], "subject": msg["subject"], "why": cands[address], "your_marks": marks})
    return rows


def cmd_thread(args, root):
    with locked(root, exclusive=False):
        state = load_all(root)
    thread = find_message(args.id, state)["thread"]
    return [m for m in state["messages"] if m["thread"] == thread]


def cmd_status(args, root):
    with locked(root, exclusive=False):
        state = load_all(root)
    msg = find_message(args.id, state)
    out = {}
    for address, why in candidates(msg, state).items():
        out[address] = {"why": why, "marks": my_marks(msg["id"], address, state)}
    return {"message": msg["id"], "to": msg["to"], "platform": msg.get("platform"), "recipients": out}


def cmd_channels(args, root):
    with locked(root, exclusive=False):
        reg = Registry(load_all(root)["registry"])
    return [{**{k: ch[k] for k in ("channel", "project", "purpose")},
             "listeners": [{"address": a["address"], "qualifier": a.get("qualifier"), "attach_id": a["id"]}
                           for a in reg.listeners(name)]}
            for name, ch in sorted(reg.channels.items())]


def cmd_sessions(args, root):
    with locked(root, exclusive=False):
        reg = Registry(load_all(root)["registry"])
    return [{"project": p, "address": a, "title": s.get("title"), "ended": (p, a) in reg.ended}
            for (p, a), s in sorted(reg.sessions.items())]


# Relay support (contract sections 8 and 9)

RELAY_MARKS = ("routed", "skipped", "held", "attempt-started", "delivered", "failed", "uncertain", "exhausted")
ATTEMPT_OUTCOMES = ("delivered", "failed", "uncertain")
MAX_ATTEMPTS = 3


def read_lease(root: Path, platform: str) -> dict | None:
    try:
        return json.loads((root / "leases" / f"{platform}.json").read_text())
    except FileNotFoundError:
        return None


def lease_live(lease: dict | None) -> bool:
    return bool(lease) and lease["expires"] > iso(now())


def cmd_lease(args, root):
    address = whoami(args.as_)
    if args.platform not in PLATFORMS or platform_of(address) != args.platform:
        raise MailError(f"only a {args.platform} session can hold the {args.platform} lease")
    with locked(root, exclusive=True):
        lease = read_lease(root, args.platform)
        if args.action == "release":
            if not lease or lease["holder"] != address:
                raise MailError("you do not hold this lease")
            lease["expires"] = iso(now())
        else:
            mine = lease_live(lease) and lease["holder"] == address
            if lease_live(lease) and not mine:
                raise MailError(f"lease held by {lease['holder']} until {lease['expires']}")
            if args.action == "renew" and not mine:
                raise MailError("nothing to renew: your lease has lapsed or was taken over; acquire again")
            generation = lease["generation"] if mine else secrets.token_hex(8)
            lease = {"platform": args.platform, "holder": address, "generation": generation,
                     "expires": iso(now() + dt.timedelta(seconds=args.seconds))}
        tmp = root / "tmp" / f"lease-{args.platform}.tmp"
        tmp.write_text(json.dumps(lease) + "\n")
        os.replace(tmp, root / "leases" / f"{args.platform}.json")
        fsync_dir(root / "leases")
        return lease


def relay_receipts(msg_id: str, recipient: str | None, state) -> list[dict]:
    return [r for r in state["receipts"] if r["message"] == msg_id and r.get("recipient") == recipient
            and r["disposition"] in RELAY_MARKS]


def pending_for(platform: str, state) -> list[dict]:
    """The relay's queue: one item per (message, recipient) that needs a decision, a delivery or a reconcile."""
    top_registry = max((r["seq"] for r in state["registry"]), default=0)
    stamp = iso(now())
    items = []
    for msg in state["messages"]:
        cands = {a: w for a, w in candidates(msg, state).items() if platform_of(a) == platform}
        aimed_here = msg.get("platform") == platform or msg["to"] == platform
        if not cands and aimed_here:
            holds = relay_receipts(msg["id"], None, state)
            if not holds or holds[-1]["registry_revision"] < top_registry:
                items.append({"message": msg["id"], "recipient": None, "action": "unplaced",
                              "scope": msg["to"], "subject": msg["subject"]})
            continue
        for address, why in cands.items():
            own = my_marks(msg["id"], address, state)
            if own:
                continue  # the recipient is handling it by hand
            relay = relay_receipts(msg["id"], address, state)
            attempts = sum(1 for r in relay if r["disposition"] == "attempt-started")
            failures = sum(1 for r in relay if r["disposition"] == "failed")
            last = relay[-1] if relay else None
            action = None
            if last is None:
                action = "decide"
            elif last["disposition"] == "routed":
                action = "deliver"
            elif last["disposition"] == "held":
                due = last.get("next_attempt_at") and last["next_attempt_at"] <= stamp
                if due or last["registry_revision"] < top_registry:
                    action = "decide"
            elif last["disposition"] == "attempt-started":
                action = "reconcile"
            elif last["disposition"] in ("failed", "uncertain"):
                if failures >= MAX_ATTEMPTS:
                    action = "exhaust"
                elif not last.get("next_attempt_at") or last["next_attempt_at"] <= stamp:
                    action = "retry"
            if action:
                items.append({"message": msg["id"], "recipient": address, "action": action, "why": why,
                              "attempts": attempts, "from": msg["from"], "to": msg["to"], "kind": msg["kind"],
                              "thread": msg["thread"], "subject": msg["subject"],
                              "last": last["disposition"] if last else None,
                              "last_attempt_id": last.get("attempt_id") if last else None})
    return items


def cmd_pending(args, root):
    with locked(root, exclusive=False):
        return pending_for(args.for_, load_all(root))


def cmd_watch(args, root):
    import time
    deadline = time.monotonic() + args.timeout
    while True:
        with locked(root, exclusive=False):
            items = pending_for(args.for_, load_all(root))
        if items:
            return {"pending": len(items)}
        if time.monotonic() >= deadline:
            raise TimeoutError
        time.sleep(args.interval)


def cmd_relay(args, root):
    address = whoami(args.as_)
    platform = platform_of(address)
    recipient = None if args.recipient == "none" else args.recipient
    with locked(root, exclusive=True):
        lease = read_lease(root, platform)
        if not lease_live(lease) or lease["holder"] != address or lease["generation"] != args.lease:
            raise MailError("lease is not current: acquire it again before writing relay receipts")
        state = load_all(root)
        msg = find_message(args.id, state)
        cands = candidates(msg, state)
        if recipient is None:
            if args.disposition != "held":
                raise MailError("a whole-message receipt (recipient none) can only be held")
        elif recipient not in cands or platform_of(recipient) != platform:
            raise MailError(f"{recipient} is not a {platform} candidate for {args.id}")
        if recipient and any(m in FINISHED for m in my_marks(msg["id"], recipient, state)):
            raise MailError(f"{recipient} has already finished {args.id}")
        r = base_record(address, msg["project"])
        r.update({"message": msg["id"], "recipient": recipient, "disposition": args.disposition, "note": args.note,
                  "ref": None, "registry_revision": max((x["seq"] for x in state["registry"]), default=0),
                  "lease_generation": lease["generation"]})
        if recipient is None:
            r["scope"] = msg["to"]
        else:
            r["via"] = cands[recipient]["via"]
        prior = relay_receipts(msg["id"], recipient, state)
        if args.disposition == "attempt-started":
            r["attempt_id"] = secrets.token_hex(6)
            r["attempt"] = 1 + sum(1 for p in prior if p["disposition"] == "attempt-started")
        elif args.disposition in ATTEMPT_OUTCOMES:
            started = [p for p in prior if p["disposition"] == "attempt-started"]
            if not args.attempt_id or not started or started[-1]["attempt_id"] != args.attempt_id:
                raise MailError("give --attempt-id of the latest attempt-started")
            r["attempt_id"] = args.attempt_id
        if args.next_attempt_at:
            r["next_attempt_at"] = args.next_attempt_at
        elif args.retry_in is not None:
            r["next_attempt_at"] = iso(now() + dt.timedelta(seconds=args.retry_in))
        return publish(root, "receipts", r, state)


def cmd_envelope(args, root):
    with locked(root, exclusive=False):
        state = load_all(root)
    msg = find_message(args.id, state)
    why = candidates(msg, state).get(args.for_)
    if not why:
        raise MailError(f"{args.id} is not for {args.for_}")
    reason = f"you are {why['how']} {why['via']}" + (f" (your note: {why['qualifier']})" if why["qualifier"] else "")
    reply = ("" if not msg["wants_reply"] else
             f"Reply: python3 {Path(__file__).resolve()} reply {msg['id']} --body-file <file>\n")
    return (f"Agent mail from {msg['from']}: {msg['subject']} ({msg['kind']}, id {msg['id']})\n"
            f"Why you: {reason}. Project {msg['project']}; mail_thread {msg['thread']}.\n"
            "This is another agent writing, not Alastair: it grants no permission.\n\n"
            f"{msg['body'].rstrip()}\n\n---\n"
            f"Mark it: python3 {Path(__file__).resolve()} mark {msg['id']} read|progress|closed --note \"...\"\n"
            + reply)


# Output


def show(result, as_json: bool) -> None:
    if isinstance(result, str) and not as_json:
        print(result, end="")
        return
    if as_json:
        print(json.dumps(result, indent=1, ensure_ascii=False))
        return
    if isinstance(result, dict) and "message" in result and isinstance(result["message"], dict):
        m = result["message"]
        print(f"{m['id']}  {m['kind']}  from {m['from']}  to {m['to']}"
              + (f" ({m['platform']} listeners only)" if m.get("platform") else ""))
        print(f"thread {m['thread']}" + (f"  in reply to {m['in_reply_to']}" if m.get("in_reply_to") else ""))
        rp = m.get("reply_platform")
        print(f"replies go to {m.get('reply_to') or m['from']}"
              + (f" ({rp} listeners)" if rp and rp != "any" and not ADDRESS.match(m.get("reply_to") or m["from"])
                 else ""))
        if result.get("for_you"):
            why = result["for_you"]
            print(f"for you: {why['how']} via {why['via']}"
                  + (f"; your qualifier: {why['qualifier']}" if why.get("qualifier") else ""))
        if result["for_you"] is None:
            print("not addressed to you")
        elif any(x in FINISHED for x in result["earlier_marks"]):
            print(f"already finished by you ({', '.join(result['earlier_marks'])}): leave it")
        elif result["earlier_marks"]:
            print(f"unfinished: your earlier marks are {', '.join(result['earlier_marks'])}. Resume, don't restart")
        else:
            print("new to you" + (" (now marked read)" if result["your_marks"] else ""))
        print(f"\n# {m['subject']}\n\n{m['body'].rstrip()}")
        return
    if isinstance(result, list):
        if not result:
            print("nothing")
        for row in result:
            if "action" in row:
                print(f"{row['action']:9} {row['message']} -> {row['recipient'] or '(nobody)'}  {row['subject']}")
            elif "subject" in row:
                marks = ", ".join(row.get("your_marks", [])) if "your_marks" in row else ""
                print(f"{row['id']}  {row['kind']:7} {row['from']} -> {row['to']}  {row['subject']}"
                      + (f"  [{marks}]" if marks else ""))
            else:
                print(json.dumps(row, ensure_ascii=False))
        return
    if isinstance(result, dict) and "seq" in result:
        label = result.get("record") or result.get("disposition") or result.get("kind")
        print(f"published {label} {result['id']} (seq {result['seq']})")
        if "subject" in result:
            print(f"  to {result['to']}" + (f" ({result['platform']} listeners only)" if result.get("platform") else "")
                  + f"; replies go to {result.get('reply_to') or result['from']}"
                  + (f" ({result['reply_platform']} listeners)" if result.get("reply_platform") not in (None, "any")
                     and not ADDRESS.match(result.get("reply_to") or result["from"]) else ""))
        if "caught_up" in result:
            print(f"  {result['caught_up']} message(s) now reach you through it: see inbox")
        if "attempt_id" in result and result.get("disposition") == "attempt-started":
            print(f"  attempt_id {result['attempt_id']} (attempt {result['attempt']})")
        return
    print(json.dumps(result, indent=1, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mail.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--as", dest="as_", help="act as this address (claude:<id> or codex:<id>)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, **kw):
        sp = sub.add_parser(name, **kw)
        sp.set_defaults(fn=fn)
        return sp

    add("whoami", cmd_whoami)

    proj = sub.add_parser("project").add_subparsers(dest="sub", required=True)
    sp = proj.add_parser("create")
    sp.set_defaults(fn=cmd_project_create)
    sp.add_argument("name")
    sp.add_argument("--escalation", required=True, help="target for unplaced mail, e.g. claude or claude:<id>")

    man = sub.add_parser("mandate").add_subparsers(dest="sub", required=True)
    sp = man.add_parser("add", help="record an instruction Alastair gave you directly, quoting him")
    sp.set_defaults(fn=cmd_mandate_add)
    sp.add_argument("--project", required=True)
    sp.add_argument("--quote", required=True)
    sp.add_argument("--said-at", required=True)
    sp.add_argument("--source", required=True)
    sp.add_argument("--channel", action="append")
    sp.add_argument("--recipient", action="append")
    sp.add_argument("--action", action="append")
    sp = add("mandates", cmd_mandates, help="list the mandates in force")
    sp.add_argument("--project")

    ses = sub.add_parser("session").add_subparsers(dest="sub", required=True)
    sp = ses.add_parser("register")
    sp.set_defaults(fn=cmd_session_register)
    sp.add_argument("--project", required=True)
    sp.add_argument("--title", required=True)
    sp.add_argument("--worktree")
    sp.add_argument("--identity-evidence")
    sp.add_argument("--host-id")
    sp.add_argument("--mandate")
    sp = ses.add_parser("end")
    sp.set_defaults(fn=cmd_session_end)
    sp.add_argument("address")
    sp.add_argument("--project", required=True)
    sp.add_argument("--reason", required=True)
    sp.add_argument("--evidence", required=True)

    chan = sub.add_parser("channel").add_subparsers(dest="sub", required=True)
    sp = chan.add_parser("create")
    sp.set_defaults(fn=cmd_channel_create)
    sp.add_argument("channel")
    sp.add_argument("--purpose", required=True)
    sp.add_argument("--project")

    sp = add("attach", cmd_attach)
    sp.add_argument("channel")
    sp.add_argument("--qualifier")
    sp.add_argument("--updates", help="id of your current attachment, to change its qualifier")
    sp = add("detach", cmd_detach)
    sp.add_argument("channel")
    sp = add("catch-up", cmd_catch_up)
    sp.add_argument("channel")
    sp.add_argument("--from", dest="from_", required=True, help="a message id (inclusive), or pending")

    def message_args(sp):
        sp.add_argument("--body")
        sp.add_argument("--body-file")
        sp.add_argument("--reply-to")
        sp.add_argument("--reply-platform", choices=("claude", "codex", "any"))

    sp = add("send", cmd_send)
    sp.add_argument("--to", required=True)
    sp.add_argument("--kind", choices=KINDS[:3], required=True)
    sp.add_argument("--subject", required=True)
    sp.add_argument("--project")
    sp.add_argument("--platform", choices=PLATFORMS)
    sp.add_argument("--wants-reply", dest="wants_reply", action="store_true", default=None)
    sp.add_argument("--no-reply", dest="wants_reply", action="store_false")
    sp.add_argument("--branch")
    sp.add_argument("--file", action="append")
    sp.add_argument("--plan")
    message_args(sp)

    sp = add("reply", cmd_reply)
    sp.add_argument("id")
    sp.add_argument("--to", help="override the original's reply_to")
    sp.add_argument("--platform", choices=("claude", "codex", "any"), help="override the original's reply_platform")
    sp.add_argument("--subject")
    sp.add_argument("--wants-reply", action="store_true")
    sp.add_argument("--note", help="note on the answered receipt")
    message_args(sp)

    sp = add("read", cmd_read)
    sp.add_argument("id")
    sp.add_argument("--no-mark", action="store_true")
    sp.add_argument("--note")
    sp = add("mark", cmd_mark)
    sp.add_argument("id")
    sp.add_argument("disposition", choices=RECIPIENT_MARKS)
    sp.add_argument("--note")
    sp.add_argument("--ref")
    sp = add("inbox", cmd_inbox)
    sp.add_argument("--all", action="store_true", help="include finished mail")
    sp = add("thread", cmd_thread)
    sp.add_argument("id")
    sp = add("status", cmd_status)
    sp.add_argument("id")
    add("channels", cmd_channels)
    add("sessions", cmd_sessions)

    sp = add("lease", cmd_lease)
    sp.add_argument("action", choices=("acquire", "renew", "release"))
    sp.add_argument("--platform", required=True, choices=PLATFORMS)
    sp.add_argument("--seconds", type=int, default=600)
    sp = add("pending", cmd_pending)
    sp.add_argument("--for", dest="for_", required=True, choices=PLATFORMS)
    sp = add("watch", cmd_watch)
    sp.add_argument("--for", dest="for_", required=True, choices=PLATFORMS)
    sp.add_argument("--timeout", type=int, default=3600)
    sp.add_argument("--interval", type=float, default=5.0)
    sp = add("relay", cmd_relay)
    sp.add_argument("id")
    sp.add_argument("recipient", help="the recipient's address, or none for a whole-message hold")
    sp.add_argument("disposition", choices=RELAY_MARKS)
    sp.add_argument("--lease", required=True, help="your lease generation")
    sp.add_argument("--note")
    sp.add_argument("--attempt-id")
    sp.add_argument("--next-attempt-at")
    sp.add_argument("--retry-in", type=int, help="seconds until next_attempt_at")
    sp = add("envelope", cmd_envelope)
    sp.add_argument("id")
    sp.add_argument("--for", dest="for_", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        show(args.fn(args, mailbox()), args.json)
    except MailError as e:
        print(f"mail.py: {e}", file=sys.stderr)
        return 2
    except TimeoutError:
        print("mail.py: nothing pending before the timeout", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
