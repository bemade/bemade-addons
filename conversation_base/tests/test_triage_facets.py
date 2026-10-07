# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
#
# Acceptance criteria (task #4331): stored computed ``unanswered``,
# ``unanswered_since``, ``last_message_date`` and ``unassigned`` on
# mail.conversation, recomputed from the messages, independent of ``state``.

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import tagged

from .common_triage import TriageCommon


class TestTriageFacets(TriageCommon):
    def test_inbound_sets_unanswered(self):
        empty = self.Conversation.create({"name": "empty"})
        self.assertFalse(empty.unanswered)
        self.assertFalse(empty.unanswered_since)
        # The only message is the creation log, dated by the wall clock when
        # it was posted. Not create_date: that is the transaction timestamp,
        # which a long test transaction (slow CI) drifts away from.
        self.assertEqual(empty.last_message_date, empty.message_ids.date)
        conv = self._inbound()
        message = conv.message_ids.filtered(lambda m: m.external_id)
        self.assertTrue(conv.unanswered)
        self.assertEqual(conv.unanswered_since, message.date)
        self.assertEqual(conv.last_message_date, message.date)
        self.assertIn(conv, self.Conversation.search([("unanswered", "=", True)]))

    def test_reply_answers(self):
        conv = self._inbound()
        reply = self._reply(conv)
        self.assertFalse(conv.unanswered)
        self.assertFalse(conv.unanswered_since)
        self.assertEqual(conv.last_message_date, reply.date)
        self.assertNotIn(conv, self.Conversation.search([("unanswered", "=", True)]))

    def test_internal_note_does_not_answer(self):
        conv = self._inbound()
        since = conv.unanswered_since
        note = conv.with_user(self.internal_user).message_post(
            body="note", subtype_xmlid="mail.mt_note"
        )
        self.assertTrue(conv.unanswered)
        self.assertEqual(conv.unanswered_since, since)
        self.assertEqual(conv.last_message_date, note.date)

    def test_captured_internal_outbound_answers(self):
        conv = self._inbound()
        self._outbound_captured(conv)
        self.assertFalse(conv.unanswered)

    def test_forward_and_record_outbound_answer(self):
        c1 = self._inbound()
        c2 = self._inbound()
        with patch.object(type(self.transport), "_send", return_value="fwd-1"):
            c1.with_user(self.internal_user).action_forward("", ["x@example.com"])
        self.assertFalse(c1.unanswered)
        c2.with_user(self.internal_user)._record_outbound(
            self.transport, "Re", "<p>b</p>", "<mid@x>"
        )
        self.assertFalse(c2.unanswered)

    def test_unanswered_stretch(self):
        conv = self._inbound()
        base = fields.Datetime.now() - timedelta(hours=10)
        first = conv.message_ids.filtered(lambda m: m.external_id)
        first.date = base
        self._outbound_captured(conv)
        conv.message_ids.sorted("id")[-1].date = base + timedelta(hours=1)
        self._inbound(conv)
        conv.message_ids.sorted("id")[-1].date = base + timedelta(hours=2)
        self._inbound(conv)
        conv.message_ids.sorted("id")[-1].date = base + timedelta(hours=3)
        self.assertTrue(conv.unanswered)
        self.assertEqual(conv.unanswered_since, base + timedelta(hours=2))
        reply = self._reply(conv)
        reply.date = base + timedelta(hours=4)
        self.assertFalse(conv.unanswered)
        self._inbound(conv)
        d = conv.message_ids.sorted("id")[-1]
        d.date = base + timedelta(hours=5)
        self.assertEqual(conv.unanswered_since, d.date)

    def test_link_mode(self):
        conv = self.Conversation._capture_stub(
            self.transport,
            self._stub(self.external),
            mode="link",
            target=self.internal_user.partner_id,
        )
        self.assertTrue(conv.unanswered)

    def test_tracking_only_messages_ignored(self):
        conv = self._inbound()
        self._reply(conv)
        last = conv.last_message_date
        conv.write({"name": "renamed", "state": "done"})
        self.assertFalse(conv.unanswered)
        self.assertEqual(conv.last_message_date, last)
        self._inbound(conv)
        self.assertTrue(conv.unanswered)
        self.assertEqual(conv.state, "done")

    def test_unassigned(self):
        team = self.env["mail.conversation.team"].create({"name": "T"})
        conv = self.Conversation.create({"name": "x", "team_id": team.id})
        self.assertTrue(conv.unassigned)
        conv.action_reassign(user=self.internal_user)
        self.assertFalse(conv.unassigned)
        self.assertNotIn(conv, self.Conversation.search([("unassigned", "=", True)]))
        conv.action_reassign(user=self.env["res.users"])
        self.assertTrue(conv.unassigned)

    def test_sortable(self):
        convs = [self._inbound() for _i in range(3)]
        base = fields.Datetime.now() - timedelta(days=1)
        # dates deliberately out of creation order
        for conv, hours in zip(convs, (2, 0, 1)):
            conv.message_ids.filtered(lambda m: m.external_id).date = base + timedelta(
                hours=hours
            )
        recs = self.Conversation.browse([c.id for c in convs])
        self.assertEqual(
            self.Conversation.search(
                [("id", "in", recs.ids)], order="unanswered_since asc"
            ).ids,
            [convs[1].id, convs[2].id, convs[0].id],
        )
        self.assertEqual(
            self.Conversation.search(
                [("id", "in", recs.ids)], order="last_message_date desc"
            ).ids,
            [convs[0].id, convs[2].id, convs[1].id],
        )

    def test_upgrade_style_recompute(self):
        unanswered = self._inbound()
        answered = self._inbound()
        self._reply(answered)
        answered.user_id = self.internal_user
        recs = unanswered | answered
        fnames = ["unanswered", "unassigned", "last_message_date", "unanswered_since"]
        self.env.flush_all()

        def snapshot():
            self.env.cr.execute(
                "SELECT id, unanswered, unassigned, last_message_date, "
                "unanswered_since FROM mail_conversation WHERE id IN %s ORDER BY id",
                (tuple(recs.ids),),
            )
            return self.env.cr.fetchall()

        before = snapshot()
        self.env.cr.execute(
            "UPDATE mail_conversation SET unanswered=NULL, unassigned=NULL, "
            "last_message_date=NULL, unanswered_since=NULL WHERE id IN %s",
            (tuple(recs.ids),),
        )
        self.Conversation.invalidate_model()
        for fname in fnames:
            self.env.add_to_compute(self.Conversation._fields[fname], recs)
        self.env.flush_all()
        self.assertEqual(snapshot(), before)


@tagged("post_install", "-at_install")
class TestTriageFacetsGateway(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        model = cls.env["ir.model"]._get("mail.conversation")
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": "conv-triage-test",
                "alias_model_id": model.id,
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.alias_email = "%s@%s" % (cls.alias.alias_name, cls.mail_alias_domain.name)
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "GW", "sendable": True}
        )

    def _mail(self, msg_id, date, in_reply_to=None):
        headers = (
            "MIME-Version: 1.0\nDate: %s\nMessage-ID: %s\nSubject: Question\n"
            "From: GW Customer <gw_triage_customer@example.com>\nTo: %s\n"
        ) % (date, msg_id, self.alias_email)
        if in_reply_to:
            headers += "In-Reply-To: %s\n" % in_reply_to
        mime = headers + 'Content-Type: text/plain; charset="UTF-8"\n\nHello.\n'
        return self.env["mail.thread"].sudo().message_process(False, mime)

    def test_gateway_inbound_then_reply(self):
        conv_id = self._mail("<gw-t-1@example.com>", "Thu, 27 Dec 2018 16:27:45 +0100")
        conv = self.env["mail.conversation"].browse(conv_id)
        first = conv.message_ids.filtered(lambda m: m.message_id == "<gw-t-1@example.com>")
        self.assertTrue(conv.unanswered)
        again = self._mail(
            "<gw-t-2@example.com>",
            "Thu, 27 Dec 2018 17:27:45 +0100",
            in_reply_to="<gw-t-1@example.com>",
        )
        self.assertEqual(again, conv_id)
        self.assertTrue(conv.unanswered)
        self.assertEqual(conv.unanswered_since, first.date)
        conv.primary_transport_id = self.transport
        with patch.object(type(self.transport), "_send", return_value="g-1"):
            conv.action_reply("<p>ok</p>")
        self.assertFalse(conv.unanswered)
