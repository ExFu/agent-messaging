"""Tests for tool/mail.py, each against its own throwaway mailbox. Run: python3 -m unittest discover tests"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MAIL = Path(__file__).resolve().parents[1] / "plugins" / "exfu-agent-messaging" / "scripts" / "mail.py"
ANA, CY, BEN, DEE = "claude:sim-ana", "claude:sim-cy", "codex:sim-ben", "codex:sim-dee"


class MailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.box = Path(self.tmp.name) / "mail"
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("AGENT_MAIL_FROM", "CLAUDE_CODE_HOST_SESSION_ID", "CODEX_THREAD_ID")}
        self.env["AGENT_MAIL_DIR"] = str(self.box)

    def tearDown(self):
        self.tmp.cleanup()

    def run_mail(self, who, *args, ok=True, stdin=None):
        p = subprocess.run([sys.executable, str(MAIL), "--json", "--as", who, *args], env=self.env,
                           capture_output=True, text=True, input=stdin)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        return p.stderr

    def setup_demo(self, attach=(ANA, CY, BEN)):
        self.run_mail(ANA, "project", "create", "demo")
        self.run_mail(ANA, "channel", "create", "demo.unlock", "--purpose", "the unlock screen")
        for who in (ANA, CY, BEN, DEE):
            self.run_mail(who, "session", "register", "--project", "demo", "--title", who)
        quals = {ANA: "copy and layout", CY: "only safety reviews", BEN: None}
        for who in attach:
            extra = ["--qualifier", quals[who]] if quals[who] else []
            self.run_mail(who, "attach", "demo.unlock", *extra)

    def inbox_ids(self, who):
        return [row["id"] for row in self.run_mail(who, "inbox")]

    def test_send_read_reply_and_reply_direction(self):
        self.setup_demo()
        ask = self.run_mail(DEE, "send", "--to", "channel:demo.unlock", "--kind", "ask", "--subject", "label?",
                            "--body", "Shorten the label?", "--reply-to", "channel:demo.unlock")
        self.assertEqual(ask["reply_platform"], "codex")
        for who in (ANA, CY, BEN):
            self.assertIn(ask["id"], self.inbox_ids(who))
        self.assertNotIn(ask["id"], self.inbox_ids(DEE))
        read = self.run_mail(ANA, "read", ask["id"])
        self.assertEqual(read["your_marks"], ["read"])
        reply = self.run_mail(ANA, "reply", ask["id"], "--body", "Done: 'Unlock'.")
        self.assertEqual((reply["to"], reply["platform"], reply["thread"]), ("channel:demo.unlock", "codex", ask["id"]))
        self.assertIn(reply["id"], self.inbox_ids(BEN))          # Codex listener gets the reply
        self.assertNotIn(reply["id"], self.inbox_ids(CY))        # Claude listener does not
        self.assertNotIn(reply["id"], self.inbox_ids(DEE))       # sender is not attached
        status = self.run_mail(DEE, "status", ask["id"])["recipients"]
        self.assertEqual(status[ANA]["marks"], ["read", "answered"])
        thread = self.run_mail(DEE, "thread", reply["id"])
        self.assertEqual([m["id"] for m in thread], [ask["id"], reply["id"]])

    def test_reply_to_unset_goes_back_to_sender_only(self):
        self.setup_demo()
        ask = self.run_mail(DEE, "send", "--to", "channel:demo.unlock", "--kind", "ask", "--subject", "q",
                            "--body", "?")
        reply = self.run_mail(ANA, "reply", ask["id"], "--body", "!")
        self.assertEqual((reply["to"], reply["platform"]), (DEE, None))
        self.assertIn(reply["id"], self.inbox_ids(DEE))
        self.assertNotIn(reply["id"], self.inbox_ids(BEN))

    def test_one_recipient_closing_does_not_hide_anothers_mail(self):
        self.setup_demo()
        req = self.run_mail(DEE, "send", "--to", "channel:demo.unlock", "--kind", "request", "--subject", "r",
                            "--body", "do it")
        self.run_mail(ANA, "mark", req["id"], "closed", "--note", "done")
        self.run_mail(CY, "mark", req["id"], "skipped", "--note", "not safety")
        self.assertNotIn(req["id"], self.inbox_ids(ANA))
        self.assertNotIn(req["id"], self.inbox_ids(CY))
        self.assertIn(req["id"], self.inbox_ids(BEN))
        self.run_mail(BEN, "mark", req["id"], "progress", "--note", "half")
        self.assertIn(req["id"], self.inbox_ids(BEN))
        err = self.run_mail(ANA, "mark", req["id"], "progress", ok=False)
        self.assertIn("already finished", err)

    def test_attach_is_future_only_and_catch_up_is_explicit(self):
        self.setup_demo(attach=(ANA,))
        early = self.run_mail(DEE, "send", "--to", "channel:demo.unlock", "--platform", "codex", "--kind", "tell",
                              "--subject", "welcome", "--body", "hi")      # no Codex listener yet
        self.run_mail(BEN, "attach", "demo.unlock")
        self.assertNotIn(early["id"], self.inbox_ids(BEN))
        self.run_mail(BEN, "catch-up", "demo.unlock", "--from", "pending")
        self.assertIn(early["id"], self.inbox_ids(BEN))
        late = self.run_mail(DEE, "send", "--to", "channel:demo.unlock", "--platform", "codex", "--kind", "tell",
                             "--subject", "later", "--body", "x")
        self.assertIn(late["id"], self.inbox_ids(BEN))            # covered by the attachment

    def test_catch_up_from_message_is_inclusive_and_bounded(self):
        self.setup_demo(attach=(ANA,))
        m1 = self.run_mail(ANA, "send", "--to", "channel:demo.unlock", "--kind", "tell", "--subject", "1", "--body", "1")
        m2 = self.run_mail(ANA, "send", "--to", "channel:demo.unlock", "--kind", "tell", "--subject", "2", "--body", "2")
        self.run_mail(CY, "catch-up", "demo.unlock", "--from", m2["id"])
        m3 = self.run_mail(ANA, "send", "--to", "channel:demo.unlock", "--kind", "tell", "--subject", "3", "--body", "3")
        ids = self.inbox_ids(CY)
        self.assertNotIn(m1["id"], ids)
        self.assertIn(m2["id"], ids)
        self.assertNotIn(m3["id"], ids)                            # after the bound, and Cy is not attached

    def test_snapshot_is_fixed_at_send(self):
        self.setup_demo(attach=(ANA,))
        msg = self.run_mail(DEE, "send", "--to", "channel:demo.unlock", "--kind", "tell", "--subject", "s",
                            "--body", "b")
        self.run_mail(BEN, "attach", "demo.unlock")
        self.assertNotIn(BEN, self.run_mail(DEE, "status", msg["id"])["recipients"])
        self.run_mail(ANA, "detach", "demo.unlock")
        self.assertIn(ANA, self.run_mail(DEE, "status", msg["id"])["recipients"])

    def test_qualifier_update_names_the_binding(self):
        self.setup_demo(attach=(ANA,))
        current = self.run_mail(ANA, "channels")[0]["listeners"][0]["attach_id"]
        self.assertIn("already attached", self.run_mail(ANA, "attach", "demo.unlock", ok=False))
        self.run_mail(ANA, "attach", "demo.unlock", "--qualifier", "copy only", "--updates", current)
        self.assertEqual(self.run_mail(ANA, "channels")[0]["listeners"][0]["qualifier"], "copy only")

    def test_refusals(self):
        self.setup_demo()
        self.assertIn("there are no roles",
                      self.run_mail(ANA, "send", "--to", "role:design", "--project", "demo", "--kind", "ask",
                                    "--subject", "x", "--body", "x", ok=False))
        self.assertIn("does not match",
                      self.run_mail(ANA, "send", "--to", "channel:demo.unlock", "--project", "other", "--kind", "ask",
                                    "--subject", "x", "--body", "x", ok=False))
        self.assertIn("not registered",
                      self.run_mail("claude:stranger", "send", "--to", "channel:demo.unlock", "--kind", "ask",
                                    "--subject", "x", "--body", "x", ok=False))
        msg = self.run_mail(ANA, "send", "--to", BEN, "--project", "demo", "--kind", "tell", "--subject", "x",
                            "--body", "x")
        self.assertIn("not addressed to", self.run_mail(CY, "mark", msg["id"], "read", ok=False))

    def test_sequence_unique_under_concurrent_writers(self):
        self.setup_demo()

        def send(i):
            return self.run_mail(ANA, "send", "--to", "channel:demo.unlock", "--kind", "tell", "--subject", str(i),
                                 "--body", str(i))
        with ThreadPoolExecutor(8) as pool:
            sent = list(pool.map(send, range(24)))
        seqs = [m["seq"] for m in sent]
        self.assertEqual(len(set(seqs)), 24)
        self.assertEqual(len({m["id"] for m in sent}), 24)
        files = sorted(os.listdir(self.box / "messages"))
        self.assertEqual(len(files), 24)
        self.assertEqual(int((self.box / "seq").read_text()), max(seqs))
        self.assertEqual(list((self.box / "tmp").iterdir()), [])

    def test_recovery_after_crashed_writers(self):
        self.setup_demo(attach=(ANA,))
        top = int((self.box / "seq").read_text())
        # Writer 1 died after linking but before updating seq: the record stands.
        msg = self.run_mail(ANA, "send", "--to", "channel:demo.unlock", "--kind", "tell", "--subject", "a",
                            "--body", "a")
        (self.box / "tmp" / f"{msg['seq']}.tmp").write_text("{}")
        (self.box / "seq").write_text(f"{top}\n")
        # Writer 2 died before linking: its record never existed.
        (self.box / "tmp" / f"{msg['seq'] + 1}.tmp").write_text("{}")
        self.assertIn(msg["id"], self.inbox_ids(CY) + [m["id"] for m in self.run_mail(DEE, "thread", msg["id"])])
        self.assertEqual(list((self.box / "tmp").iterdir()), [])
        self.assertEqual(int((self.box / "seq").read_text()), msg["seq"])
        nxt = self.run_mail(ANA, "send", "--to", "channel:demo.unlock", "--kind", "tell", "--subject", "b",
                            "--body", "b")
        self.assertEqual(nxt["seq"], msg["seq"] + 1)

    def test_read_reports_marks_from_before_this_read(self):
        self.setup_demo()
        m = self.run_mail(DEE, "send", "--to", "channel:demo.unlock", "--kind", "ask", "--subject", "s",
                          "--body", "b")["id"]
        first = self.run_mail(ANA, "read", m)
        self.assertEqual((first["earlier_marks"], first["your_marks"]), ([], ["read"]))
        self.run_mail(ANA, "mark", m, "progress", "--note", "half")
        again = self.run_mail(ANA, "read", m)
        self.assertEqual(again["earlier_marks"], ["read", "progress"])

    def test_catch_up_reports_what_it_brought(self):
        self.setup_demo(attach=(ANA,))
        for i in range(2):
            self.run_mail(ANA, "send", "--to", "channel:demo.unlock", "--kind", "tell", "--subject", str(i),
                          "--body", "x")
        self.assertEqual(self.run_mail(CY, "catch-up", "demo.unlock", "--from", "pending")["caught_up"], 2)

    def test_new_lists_who_to_nudge_since_a_seq(self):
        self.setup_demo()
        start = self.run_mail(ANA, "new", "--for", "claude")["latest"]
        m1 = self.run_mail(DEE, "send", "--to", "channel:demo.unlock", "--kind", "ask", "--subject", "s",
                           "--body", "b")
        m2 = self.run_mail(DEE, "send", "--to", BEN, "--project", "demo", "--kind", "tell", "--subject", "t",
                           "--body", "b")
        out = self.run_mail(ANA, "new", "--for", "claude", "--since", str(start))
        self.assertEqual(out["latest"], m2["seq"])
        rows = {r["id"]: r["for"] for r in out["messages"]}
        self.assertEqual(sorted(rows[m1["id"]]), sorted([ANA, CY]))   # Ben is Codex's to nudge
        self.assertEqual(rows[m2["id"]], [])
        self.run_mail(ANA, "mark", m1["id"], "closed")
        again = self.run_mail(ANA, "new", "--for", "claude", "--since", str(start))
        self.assertEqual({r["id"]: r["for"] for r in again["messages"]}[m1["id"]], [CY])   # finished: no nudge
        self.assertEqual(self.run_mail(ANA, "new", "--for", "claude", "--since", str(out["latest"]))["messages"], [])
        both = self.run_mail(ANA, "new", "--for", "all", "--since", str(start))
        self.assertEqual({r["id"]: sorted(r["for"]) for r in both["messages"]}[m2["id"]], [BEN])

    def test_nudges_one_per_session_ready_to_send(self):
        self.setup_demo()
        start = self.run_mail(ANA, "nudges")["latest"]
        m1 = self.run_mail(DEE, "send", "--to", "channel:demo.unlock", "--kind", "ask", "--subject", "s",
                           "--body", "b")
        self.run_mail(CY, "send", "--to", "channel:demo.unlock", "--kind", "tell", "--subject", "t", "--body", "b")
        out = self.run_mail(ANA, "nudges", "--since", str(start))
        self.assertEqual(out["latest"], m1["seq"] + 1)
        by = {n["to"]: n for n in out["nudges"]}
        # The asker (ANA here) is listed like anyone else: identity never filters the router's list (13 Nov 2026).
        self.assertEqual(sorted(by), sorted([ANA, CY, BEN]))
        self.assertEqual(by[ANA]["messages"], 2)
        self.assertEqual(by[CY]["messages"], 1)   # not nudged for its own message
        self.assertEqual((by[BEN]["platform"], by[BEN]["target"]), ("codex", "sim-ben"))
        self.assertEqual((by[ANA]["platform"], by[ANA]["target"]), ("claude", "sim-ana"))
        self.assertIn(f"(2 messages, from {DEE}, {CY})", by[ANA]["text"])
        self.assertIn("(1 message, from", by[CY]["text"])
        self.assertTrue(by[ANA]["text"].endswith(f"Run: python3 {MAIL} inbox"))
        self.run_mail(BEN, "mark", m1["id"], "closed")
        again = {n["to"]: n["messages"] for n in self.run_mail(ANA, "nudges", "--since", str(start))["nudges"]}
        self.assertEqual(again[BEN], 1)   # finished mail drops out of the count
        claude_only = self.run_mail(ANA, "nudges", "--for", "claude", "--since", str(start))["nudges"]
        self.assertEqual(sorted(n["to"] for n in claude_only), sorted([ANA, CY]))
        self.assertEqual(self.run_mail(ANA, "nudges", "--since", str(out["latest"]))["nudges"], [])

    def test_watch_wakes_on_a_newer_message(self):
        self.setup_demo()
        latest = self.run_mail(ANA, "new", "--for", "claude")["latest"]
        p = subprocess.run([sys.executable, str(MAIL), "--as", ANA, "watch", "--since", str(latest), "--timeout", "1",
                            "--interval", "0.2"], env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.run_mail(DEE, "send", "--to", "channel:demo.unlock", "--kind", "tell", "--subject", "s", "--body", "b")
        self.assertGreater(self.run_mail(ANA, "watch", "--since", str(latest), "--timeout", "1")["latest"], latest)

    def test_records_are_never_overwritten(self):
        self.setup_demo()
        before = {p.name: p.read_bytes() for p in (self.box / "registry").iterdir()}
        self.run_mail(ANA, "attach", "demo.unlock", ok=False)
        after = {p.name: p.read_bytes() for p in (self.box / "registry").iterdir()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
