"""Use case: a reply stays on the record it answers, even when addressed to
a team inbox that creates other records (core reads that as a forward).

Acceptance criteria:
- AC1: setting « Send from the signature address » on: a reply (In-Reply-To
  a message of a record) addressed to an inbox of another model lands on
  the record, as a reply to that message; no record is created.
- AC2: setting off: core behaviour (a new record through the inbox), for
  every model (no per-model exception: the setting alone turns the rule on).
- AC3: a fresh email (no In-Reply-To) to the inbox still creates a record.
- AC4: hook ``_mail_on_alias_reply(aliases, message_dict)`` on the record,
  called after the reply is posted, when an inbox of another model was among
  the recipients: kept by AC1 (inbox in To) or routed by core (inbox in Cc).
- AC5: a failing hook never changes where the reply lands.
"""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common_sender import SenderCommon


@tagged("post_install", "-at_install")
class TestReplyRouting(SenderCommon):
    def setUp(self):
        super().setUp()
        self.sent, _mail = self._post(self.u_full)

    def _raw(self, to, cc="", in_reply_to="", subject="RE: Sender Document"):
        headers = [
            f"From: Sender Supplier <{self.external.email}>",
            f"To: {to}",
            f"Subject: {subject}",
            "Message-ID: <reply-routing-1@supplier.example.com>",
            "Date: Mon, 02 Nov 2026 10:00:00 -0500",
            "MIME-Version: 1.0",
            'Content-Type: text/plain; charset="utf-8"',
        ]
        if cc:
            headers.append(f"Cc: {cc}")
        if in_reply_to:
            headers += [f"In-Reply-To: {in_reply_to}", f"References: {in_reply_to}"]
        return "\r\n".join(headers) + "\r\n\r\nThanks, see below.\r\n"

    def _process(self, **kwargs):
        with self.mock_mail_gateway():
            return self.env["mail.thread"].message_process(None, self._raw(**kwargs))

    def _jobs(self):
        return self.env["hr.job"].search([("name", "ilike", "Sender Document")])

    def _replies(self):
        return self.document.message_ids.filtered(lambda m: m.message_type == "email")

    def test_ac1_reply_kept_on_record(self):
        self._setting()
        thread_id = self._process(to=self.alias_email, in_reply_to=self.sent.message_id)
        self.assertEqual(thread_id, self.document.id)
        self.assertFalse(self._jobs(), "no record created through the inbox")
        reply = self._replies()
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply.parent_id, self.sent)

    def test_ac2_setting_off_core_forward(self):
        self._process(to=self.alias_email, in_reply_to=self.sent.message_id)
        self.assertEqual(len(self._jobs()), 1)
        self.assertFalse(self._replies())

    def test_ac2_no_model_exception(self):
        self.assertFalse(
            hasattr(self.env["mail.thread"], "_mail_reply_always_kept_models"),
            "no per-model opt-in: the company setting alone decides",
        )

    def test_ac3_fresh_email_creates_record(self):
        self._setting()
        self._process(to=self.alias_email, subject="Sender Document question")
        self.assertEqual(len(self._jobs()), 1)
        self.assertFalse(self._replies())

    def _capture_hook(self):
        calls = []
        Department = type(self.env["res.partner"])

        def hook(record, aliases, message_dict):
            calls.append((record, aliases, record._mail_reply_landed(message_dict)))

        def landed(record, message_dict):
            return bool(record.message_ids.filtered(lambda m: m.message_id == message_dict["message_id"]))

        return calls, patch.multiple(
            Department, _mail_on_alias_reply=hook, _mail_reply_landed=landed, create=True
        )

    def test_ac4_hook_inbox_in_to(self):
        self._setting()
        calls, patcher = self._capture_hook()
        with patcher:
            self._process(to=self.alias_email, in_reply_to=self.sent.message_id)
        self.assertEqual(len(calls), 1)
        record, aliases, landed = calls[0]
        self.assertEqual(record, self.document)
        self.assertEqual(aliases, self.alias)
        self.assertTrue(landed, "called after the reply is posted")

    def test_ac4_hook_inbox_in_cc(self):
        calls, patcher = self._capture_hook()
        with patcher:
            thread_id = self._process(
                to="someone@supplier.example.com", cc=self.alias_email, in_reply_to=self.sent.message_id
            )
        self.assertEqual(thread_id, self.document.id)
        self.assertEqual(len(calls), 1)

    def test_ac5_failing_hook(self):
        self._setting()
        Department = type(self.env["res.partner"])

        def boom(record, aliases, message_dict):
            raise RuntimeError("boom")

        with patch.object(Department, "_mail_on_alias_reply", boom), mute_logger(
            "odoo.addons.mail_company_signature.models.mail_thread"
        ):
            thread_id = self._process(to=self.alias_email, in_reply_to=self.sent.message_id)
        self.assertEqual(thread_id, self.document.id)
        self.assertEqual(len(self._replies()), 1)
