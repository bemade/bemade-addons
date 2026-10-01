# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
#
# Acceptance criteria (task #4331): an inbound message reopens a ``waiting``
# conversation; nothing else (answers, notes, tracking) does; other states
# are left alone; the per-user handled/snooze state is never touched.

from datetime import timedelta

from odoo import fields
from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import tagged

from .common_triage import TriageCommon


class TestWaitingReopen(TriageCommon):
    def test_inbound_reopens_waiting(self):
        conv = self._inbound()
        conv.state = "waiting"
        self._inbound(conv)
        self.assertEqual(conv.state, "open")

    def test_non_inbound_does_not_reopen(self):
        conv = self._inbound()
        conv.state = "waiting"
        self._reply(conv)
        self.assertEqual(conv.state, "waiting")
        conv.with_user(self.internal_user).message_post(
            body="note", subtype_xmlid="mail.mt_note"
        )
        self.assertEqual(conv.state, "waiting")
        self._outbound_captured(conv)
        self.assertEqual(conv.state, "waiting")
        conv.name = "renamed"
        self.assertEqual(conv.state, "waiting")

    def test_other_states_keep_state(self):
        for state in ("open", "snoozed", "done"):
            conv = self._inbound()
            conv.state = state
            self._inbound(conv)
            self.assertEqual(conv.state, state)

    def test_checkmark_durability(self):
        conv = self._inbound()
        until = fields.Datetime.now() + timedelta(hours=1)
        member = self.env["mail.conversation.member"].create(
            {
                "conversation_id": conv.id,
                "user_id": self.internal_user.id,
                "is_handled": True,
                "snooze_until": until,
            }
        )
        conv.state = "waiting"
        self._inbound(conv)
        self.assertTrue(member.is_handled)
        self.assertEqual(member.snooze_until, until)


@tagged("post_install", "-at_install")
class TestWaitingReopenGateway(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        model = cls.env["ir.model"]._get("mail.conversation")
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": "conv-reopen-test",
                "alias_model_id": model.id,
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.alias_email = "%s@%s" % (cls.alias.alias_name, cls.mail_alias_domain.name)

    def _mail(self, msg_id, in_reply_to=None):
        headers = (
            "MIME-Version: 1.0\nDate: Thu, 27 Dec 2018 16:27:45 +0100\n"
            "Message-ID: %s\nSubject: Question\n"
            "From: GW Customer <gw_reopen_customer@example.com>\nTo: %s\n"
        ) % (msg_id, self.alias_email)
        if in_reply_to:
            headers += "In-Reply-To: %s\n" % in_reply_to
        mime = headers + 'Content-Type: text/plain; charset="UTF-8"\n\nHello.\n'
        return self.env["mail.thread"].sudo().message_process(False, mime)

    def test_gateway_inbound_reopens_waiting(self):
        conv = self.env["mail.conversation"].browse(self._mail("<gw-r-1@example.com>"))
        until = fields.Datetime.now() + timedelta(hours=1)
        member = self.env["mail.conversation.member"].create(
            {
                "conversation_id": conv.id,
                "user_id": self.env.ref("base.user_admin").id,
                "is_handled": True,
                "snooze_until": until,
            }
        )
        conv.state = "waiting"
        self._mail("<gw-r-2@example.com>", in_reply_to="<gw-r-1@example.com>")
        self.assertEqual(conv.state, "open")
        self.assertTrue(member.is_handled)
        self.assertEqual(member.snooze_until, until)
