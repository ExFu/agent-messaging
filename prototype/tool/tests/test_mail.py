"""Agent mail (planning/T3-agent-mail.md): the mailbox, receipts, queues and routing rules, in a throwaway folder.

    python3 -m unittest discover -s scripts/agent-mail/tests -v
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mail  # noqa: E402

CLAUDE_A = "claude:local_aaaa"
CLAUDE_B = "claude:local_bbbb"
ORCH = "claude:local_orch"
CODEX = "codex:thread-1"


class MailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock_env({"AGENT_MAIL_DIR": self.tmp.name, "AGENT_MAIL_FROM": CLAUDE_A})
        self.env.__enter__()
        self.root = mail.mail_root()

    def tearDown(self):
        self.env.__exit__(None, None, None)
        self.tmp.cleanup()

    def run_cli(self, *argv: str, who: str | None = None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock_env({"AGENT_MAIL_FROM": who} if who else {}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = mail.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def send(self, who: str, to: str, kind: str = "ask", subject: str = "Hello", body: str = "Body", *extra: str) -> dict:
        code, out, err = self.run_cli("send", "--json", "--to", to, "--kind", kind, "--subject", subject,
                                      "--body", body, *extra, who=who)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def events(self, msg_id: str) -> list[str]:
        return [r["event"] for r in mail.receipts(self.root, msg_id)]

    # Sending and replying

    def test_send_fills_in_sender_reply_to_thread_and_git_context(self):
        msg = self.send(CLAUDE_A, "codex")
        self.assertEqual(msg["from"], CLAUDE_A)
        self.assertEqual(msg["reply_to"], CLAUDE_A)
        self.assertEqual(msg["thread"], msg["id"])
        self.assertTrue(msg["wants_reply"])
        self.assertIn("branch", msg["context"])
        self.assertTrue((self.root / "messages" / f"{msg['id']}.json").is_file())

    def test_tell_wants_no_reply_unless_asked(self):
        self.assertFalse(self.send(CLAUDE_A, "codex", "tell")["wants_reply"])
        self.assertTrue(self.send(CLAUDE_A, "codex", "tell", "S", "B", "--wants-reply")["wants_reply"])

    def test_reply_goes_to_reply_to_in_the_same_thread_and_marks_the_original_answered(self):
        ask = self.send(CLAUDE_A, "codex", "ask", "Which card?", "Q", "--reply-to", CLAUDE_B)
        code, out, err = self.run_cli("reply", "--json", ask["id"], "--body", "KitCard", who=CODEX)
        self.assertEqual(code, 0, err)
        reply = json.loads(out)
        self.assertEqual(reply["to"], CLAUDE_B)
        self.assertEqual(reply["thread"], ask["thread"])
        self.assertEqual(reply["in_reply_to"], ask["id"])
        self.assertEqual(reply["subject"], "Re: Which card?")
        self.assertEqual(reply["kind"], "reply")
        self.assertEqual(self.events(ask["id"]), ["answered"])

    def test_a_tell_in_the_thread_is_not_an_answer(self):
        ask = self.send(CODEX, "claude:orchestrator", "request", "Build it", "B")
        code, out, err = self.run_cli("reply", "--json", ask["id"], "--kind", "tell", "--body", "local_b owns it", who=ORCH)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["to"], CODEX)
        self.assertEqual(self.events(ask["id"]), [])

    def test_ids_sort_by_time(self):
        ids = [self.send(CLAUDE_A, "codex")["id"] for _ in range(5)]
        self.assertEqual(ids, sorted(ids))

    def test_bad_input_is_refused_without_writing(self):
        for argv in (["send", "--to", "gemini", "--subject", "S", "--body", "B"],
                     ["send", "--to", "codex:a:b", "--subject", "S", "--body", "B"],
                     ["send", "--to", "codex", "--subject", " ", "--body", "B"],
                     ["send", "--to", "codex", "--subject", "S"]):
            code, _, err = self.run_cli(*argv)
            self.assertEqual(code, 2, argv)
            self.assertTrue(err.startswith("mail.py: "), err)
        self.assertEqual(mail.all_messages(self.root), [])

    def test_the_desktop_session_id_is_the_claude_address(self):
        with mock_env({"AGENT_MAIL_FROM": None, "CLAUDE_CODE_HOST_SESSION_ID": "local_1234"}):
            self.assertEqual(mail.my_address(), "claude:local_1234")
        with mock_env({"AGENT_MAIL_FROM": None, "CLAUDE_CODE_HOST_SESSION_ID": None}):
            with self.assertRaises(mail.MailError):
                mail.my_address()

    # Queues

    def test_router_queue_holds_claude_mail_until_delivered_or_closed(self):
        a = self.send(CODEX, CLAUDE_A)
        b = self.send(CODEX, "claude")
        c = self.send(CODEX, "claude:orchestrator")
        self.send(CLAUDE_A, "codex")
        self.assertEqual([m["id"] for m in mail.pending(self.root, "claude")], [a["id"], b["id"], c["id"]])
        self.run_cli("mark", a["id"], "routed", "--target", CLAUDE_A, who="claude:router")
        self.assertEqual(len(mail.pending(self.root, "claude")), 3, "routed alone is not done")
        self.run_cli("mark", a["id"], "delivered", "--target", CLAUDE_A, who="claude:router")
        self.run_cli("mark", b["id"], "failed", "--note", "gone", who="claude:router")
        self.assertIn(b["id"], [m["id"] for m in mail.pending(self.root, "claude")], "a failure still has to go somewhere")
        self.run_cli("mark", b["id"], "delivered", "--target", ORCH, who="claude:router")
        self.run_cli("mark", c["id"], "closed", who="claude:router")
        self.assertEqual(mail.pending(self.root, "claude"), [])
        self.assertEqual(len(mail.pending(self.root, "codex")), 1)

    def test_held_mail_leaves_the_queue_until_something_else_happens_to_it(self):
        msg = self.send(CODEX, "claude:orchestrator")
        self.run_cli("mark", msg["id"], "held", "--note", "no orchestrator", who="claude:router")
        self.assertEqual(mail.pending(self.root, "claude"), [])
        self.assertEqual(len(mail.pending(self.root, "claude", include_held=True)), 1)
        self.run_cli("mark", msg["id"], "routed", "--target", ORCH, who="claude:router")
        self.assertEqual(len(mail.pending(self.root, "claude")), 1)

    def test_inbox_is_unread_until_the_readers_platform_reads_it(self):
        msg = self.send(CODEX, CLAUDE_A)
        self.send(CODEX, CLAUDE_B)
        self.run_cli("mark", msg["id"], "delivered", "--target", CLAUDE_A, who="claude:router")
        self.assertEqual([m["id"] for m in mail.unread(self.root, CLAUDE_A, [])], [msg["id"]])
        code, out, _ = self.run_cli("read", msg["id"], who=CLAUDE_A)
        self.assertEqual(code, 0)
        self.assertIn("Subject: Hello", out)
        self.assertEqual(mail.unread(self.root, CLAUDE_A, []), [])

    def test_peek_leaves_no_receipt(self):
        msg = self.send(CODEX, CLAUDE_A)
        self.run_cli("read", "--peek", msg["id"])
        self.assertEqual(self.events(msg["id"]), [])

    def test_codex_inbox_by_platform(self):
        msg = self.send(CLAUDE_A, "codex")
        self.send(CLAUDE_A, CODEX)
        code, out, _ = self.run_cli("inbox", "--json", "--for", "codex", who=CODEX)
        self.assertEqual(len(json.loads(out)), 2)
        self.run_cli("read", msg["id"], who=CODEX)
        code, out, _ = self.run_cli("inbox", "--json", "--for", "codex", who=CODEX)
        self.assertEqual(len(json.loads(out)), 1)

    def test_the_orchestrators_inbox_includes_its_role_address(self):
        self.run_cli("register", "--role", "orchestrator", "--title", "Main", who=ORCH)
        msg = self.send(CODEX, "claude:orchestrator")
        self.assertEqual([m["id"] for m in mail.unread(self.root, ORCH, mail.role_aliases(self.root, ORCH))], [msg["id"]])
        self.assertEqual(mail.role_aliases(self.root, CLAUDE_A), [])

    # Routing rules

    def test_suggest_follows_the_fixed_rules(self):
        self.run_cli("register", "--role", "orchestrator", who=ORCH)
        addressed = self.send(CODEX, CLAUDE_B)
        role = self.send(CODEX, "claude:orchestrator")
        ask = self.send(CLAUDE_A, "codex", "ask", "Q", "B")
        reply = self.send(CODEX, "claude", "reply", "Re", "A", "--in-reply-to", ask["id"], "--thread", ask["thread"])
        later = self.send(CODEX, "claude", "tell", "More", "B", "--thread", ask["thread"])
        fresh = self.send(CODEX, "claude", "request", "Build it", "B")
        cases = {addressed["id"]: (CLAUDE_B, "addressed"), role["id"]: (ORCH, "role"),
                 reply["id"]: (CLAUDE_A, "reply"), later["id"]: (CLAUDE_A, "thread"), fresh["id"]: (None, "content")}
        for msg_id, (target, rule) in cases.items():
            guess = mail.suggest(self.root, mail.load_message(self.root, msg_id))
            self.assertEqual((guess["target"], guess["rule"]), (target, rule), msg_id)
        self.assertEqual(mail.suggest(self.root, mail.load_message(self.root, fresh["id"]))["orchestrator"], ORCH)

    def test_an_unregistered_role_is_left_for_the_router(self):
        msg = self.send(CODEX, "claude:orchestrator")
        self.assertEqual(mail.suggest(self.root, msg)["rule"], "no-role")

    def test_the_newest_registration_holds_a_role(self):
        self.run_cli("register", "--role", "orchestrator", who=CLAUDE_A)
        self.run_cli("register", "--role", "orchestrator", who=ORCH)
        code, out, _ = self.run_cli("who", "--role", "orchestrator", "--address-only")
        self.assertEqual(out.strip(), ORCH)

    # Delivery text and watching

    def test_envelope_opens_with_a_self_contained_line_and_says_how_to_reply(self):
        msg = self.send(CODEX, CLAUDE_A, "ask", "Which card?", "x" * (mail.ENVELOPE_BODY_LIMIT + 50))
        code, out, _ = self.run_cli("envelope", msg["id"])
        first = out.splitlines()[0]
        self.assertEqual(first, f"Agent mail from {CODEX}: Which card? (ask, wants a reply).")
        self.assertIn(f"reply {msg['id']} --body-file", out)
        self.assertIn("[cut at", out)
        tell = self.send(CODEX, CLAUDE_A, "tell", "Landed", "Done.")
        code, out, _ = self.run_cli("envelope", tell["id"])
        self.assertIn("(tell, no reply needed)", out)
        self.assertIn(f"read {tell['id']}", out)
        self.assertNotIn("reply " + tell["id"], out)

    def test_watch_once_returns_at_once_when_mail_waits_and_times_out_when_none(self):
        code, out, _ = self.run_cli("watch", "--once", "--timeout", "0.2", "--interval", "0.05")
        self.assertEqual(code, 0)
        self.assertIn("timed out", out)
        msg = self.send(CODEX, "claude")
        code, out, _ = self.run_cli("watch", "--once", "--interval", "0.05")
        self.assertIn(msg["id"], out)

    def test_concurrent_writers_never_lose_or_corrupt_a_message(self):
        def burst(sender):
            for i in range(40):
                mail.post(self.root, mail.make_message(sender, "codex" if sender.startswith("claude") else "claude",
                                                       "tell", f"n{i}", "b"))
        threads = [threading.Thread(target=burst, args=(s,)) for s in (CLAUDE_A, CLAUDE_B, CODEX, ORCH)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(mail.all_messages(self.root)), 160)
        self.assertEqual(list((self.root / "tmp").iterdir()), [])


@contextlib.contextmanager
def _env(values: dict):
    saved = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def mock_env(values: dict):
    return _env(values)


if __name__ == "__main__":
    unittest.main()
