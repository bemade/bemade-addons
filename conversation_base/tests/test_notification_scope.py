# Acceptance criteria (AC5/AC6): mail.conversation is opted into
# mail_notification_scope by shipped data, and on EVERY notify entry path the
# conversation produces no email at all -- external followers/participants
# are never emailed, internal email-preferring users get an in-app
# notification instead.
#   6.  the opt-in ships as data (conversation yes, other models no);
#   7.  internal note naming an external + an internal user;
#   8.  action_reply to two addresses: transport._send only, no copies;
#   9.  inbound Cc of an existing external partner never causes an email;
#   10. assignment (auto-subscribe), tracking and message_notify paths;
#   11. chatter composer and scheduled posts;
#   12. out-of-office auto-reply is skipped (scoped), but not elsewhere.

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from .common import ConversationNotifyCommon


@tagged("post_install", "-at_install")
class TestConversationNotificationScope(ConversationNotifyCommon):
    def setUp(self):
        super().setUp()
        self._follow_all(self.conversation, self.external)

    def test_06_opt_in_ships_as_data(self):
        self.assertTrue(self.env["mail.conversation"]._notification_scope_applies())
        self.assertFalse(self.env["res.partner"]._notification_scope_applies())

    def test_07_internal_note(self):
        with self.mock_mail_gateway():
            message = self.conversation.message_post(
                body="note",
                subtype_xmlid="mail.mt_note",
                partner_ids=[self.external.id, self.assignee.partner_id.id],
            )
            self.env.flush_all()
        self.assertFalse(self._all_mails())
        self.assertEqual(
            self._notifs(message, self.assignee.partner_id).notification_type, "inbox"
        )
        self.assertFalse(self._notifs(message, self.external))

    def test_08_reply_to_two(self):
        self.conversation.user_id = self.assignee
        self.env.flush_all()
        before = self._all_mails()
        with patch.object(
            type(self.transport), "_send", autospec=True, return_value="ext-1"
        ) as mocked_send, self.mock_mail_gateway():
            message = self.conversation.action_reply(
                "<p>x</p>", recipients=["a@example.com", "b@example.com"]
            )
            self.env.flush_all()
        mocked_send.assert_called_once()
        self.assertEqual(
            mocked_send.call_args.kwargs.get("recipients"),
            ["a@example.com", "b@example.com"],
        )
        self.assertEqual(self._all_mails(), before)
        self.assertEqual(
            self._notifs(message, self.assignee.partner_id).notification_type, "inbox"
        )
        self.assertFalse(self._notifs(message, self.external))

    def test_09_inbound_cc_existing_partner(self):
        with self.mock_mail_gateway():
            conv_id = self._inbound(
                "<scope-cc-1@example.com>", cc=self.external.email
            )
            self.env.flush_all()
        conversation = self.env["mail.conversation"].browse(conv_id)
        cc = conversation.participant_ids.filtered(
            lambda p: p.email_normalized == self.external.email
        )
        self.assertEqual(cc.role, "cc")
        self.assertNotIn(self.external, conversation.message_partner_ids)
        self.assertFalse(self._mails_to(self.external.email))
        conversation.primary_transport_id = self.transport
        with self.mock_mail_gateway():
            conversation.message_post(body="later", subtype_xmlid="mail.mt_comment")
            self.env.flush_all()
        self.assertFalse(self._mails_to(self.external.email))
        with patch.object(
            type(self.transport), "_send", autospec=True, return_value="ext-2"
        ) as mocked_send, self.mock_mail_gateway():
            conversation.action_reply("<p>y</p>", recipients=["other@example.com"])
            self.env.flush_all()
            self.assertNotIn(
                self.external.email, mocked_send.call_args.kwargs["recipients"]
            )
            conversation.action_reply("<p>z</p>", recipients=[self.external.email])
            self.env.flush_all()
        self.assertEqual(
            mocked_send.call_args.kwargs["recipients"], [self.external.email]
        )
        self.assertFalse(self._mails_to(self.external.email))
        # threaded follow-up (message_update path) with the partner in To:
        with self.mock_mail_gateway():
            self._inbound(
                "<scope-cc-2@example.com>",
                in_reply_to="<scope-cc-1@example.com>",
                to="%s, %s" % (self.alias_email, self.external.email),
            )
            self.env.flush_all()
        self.assertFalse(self._mails_to(self.external.email))

    def test_10_assignment_tracking_and_notify(self):
        with self.mock_mail_gateway():
            self.conversation.with_user(self.other_internal).write(
                {"user_id": self.assignee.id}
            )
            self.env.flush_all()
        self.assertFalse(self._all_mails())
        self.assertTrue(
            self.env["mail.notification"].sudo().search(
                [
                    ("res_partner_id", "=", self.assignee.partner_id.id),
                    ("mail_message_id.res_id", "=", self.conversation.id),
                    ("mail_message_id.model", "=", "mail.conversation"),
                    ("notification_type", "=", "inbox"),
                ]
            )
        )
        with self.mock_mail_gateway():
            self.conversation.write({"state": "waiting"})
            self.env.flush_all()
        self.assertFalse(self._all_mails())
        with self.mock_mail_gateway():
            self.conversation.message_notify(
                partner_ids=[self.external.id, self.assignee.partner_id.id],
                body="direct",
                subject="s",
            )
            self.env.flush_all()
        self.assertFalse(self._all_mails())

    def test_11_composer_and_scheduled(self):
        with self.mock_mail_gateway():
            ctx = {
                "default_model": "mail.conversation",
                "default_res_ids": self.conversation.ids,
                "default_composition_mode": "comment",
            }
            composer = self.env["mail.compose.message"].with_context(**ctx).create(
                {
                    "body": "<p>hi</p>",
                    "partner_ids": [(6, 0, self.external.ids)],
                }
            )
            composer._action_send_mail()
            self.env.flush_all()
        self.assertFalse(self._all_mails())
        with self.mock_mail_gateway():
            self.conversation.message_post(
                body="later",
                subtype_xmlid="mail.mt_comment",
                partner_ids=self.external.ids,
                scheduled_date=fields.Datetime.now() - timedelta(minutes=5),
            )
            self.env["mail.message.schedule"].sudo()._send_notifications_cron()
            self.env.flush_all()
        self.assertFalse(self._mails_to(self.external.email))

    def _set_out_of_office(self):
        self.assignee.write(
            {
                "out_of_office_from": fields.Datetime.now() - timedelta(days=1),
                "out_of_office_to": fields.Datetime.now() + timedelta(days=1),
                "out_of_office_message": "<p>Away</p>",
            }
        )
        self.env.flush_all()

    def _ooo_messages(self, record):
        return self.env["mail.message"].sudo().search(
            [
                ("model", "=", record._name),
                ("res_id", "=", record.id),
                ("message_type", "=", "out_of_office"),
            ]
        )

    def test_12_out_of_office(self):
        self._set_out_of_office()
        self.conversation.user_id = self.assignee
        with self.mock_mail_gateway():
            self.conversation.message_post(
                body="question",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                author_id=self.external.id,
            )
            self.env.flush_all()
        self.assertFalse(self._ooo_messages(self.conversation))
        self.assertFalse(self._mails_to(self.external.email))
        # negative control: an unscoped thread still auto-replies
        partner_thread = self.env["res.partner"].create(
            {"name": "OOO thread", "user_id": self.assignee.id}
        )
        with self.mock_mail_gateway():
            partner_thread.message_post(
                body="question",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                author_id=self.external.id,
            )
            self.env.flush_all()
        self.assertTrue(self._ooo_messages(partner_thread))
        self.assertTrue(self._mails_to(self.external.email))
