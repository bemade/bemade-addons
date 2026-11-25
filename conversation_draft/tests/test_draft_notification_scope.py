# Acceptance criteria (draft comments are opted into mail_notification_scope):
#   * The opt-in ships as data; the gate is active for the draft model only.
#   * An internal user who prefers email gets an inbox notification and no
#     mail.mail is created, for notes and comments, by mention or as follower.
#   * No out-of-office auto-reply is produced.
#   * Archiving the rule restores the prior behaviour, and externals stay
#     excluded by the draft's own filter.

from datetime import timedelta

from odoo import Command, fields

from .common import DraftCommon


class TestDraftNotificationScope(DraftCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_email = cls.env["res.users"].create(
            {
                "name": "Email Pref",
                "login": "draft_email_pref",
                "email": "draft_email_pref@example.com",
                "notification_type": "email",
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )
        cls.rule = cls.env.ref(
            "conversation_draft.mail_notification_scope_mail_conversation_draft"
        )

    def _post(self, draft, subtype, **kwargs):
        message = draft.message_post(
            body="Please review", subtype_xmlid=subtype, **kwargs
        )
        self.env.flush_all()
        return message

    def _notifications(self, message):
        return self.env["mail.notification"].search(
            [("mail_message_id", "=", message.id)]
        )

    def _mails(self, message):
        return self.env["mail.mail"].search([("mail_message_id", "=", message.id)])

    def test_opt_in_ships_as_data(self):
        self.assertTrue(self.rule.active)
        self.assertEqual(self.rule.model, "mail.conversation.draft")
        self.assertTrue(self.Draft._notification_scope_applies())
        self.assertFalse(self.env["res.partner"]._notification_scope_applies())

    def test_email_preference_user_gets_inbox_not_email(self):
        draft = self._open_draft()
        partner = self.user_email.partner_id
        for subtype in ("mail.mt_comment", "mail.mt_note"):
            message = self._post(draft, subtype, partner_ids=[partner.id])
            notifications = self._notifications(message).filtered(
                lambda n: n.res_partner_id == partner
            )
            self.assertEqual(notifications.mapped("notification_type"), ["inbox"])
            self.assertFalse(self._mails(message))
        # as a follower rather than by mention
        draft.message_subscribe([partner.id])
        message = self._post(draft, "mail.mt_comment")
        notifications = self._notifications(message).filtered(
            lambda n: n.res_partner_id == partner
        )
        self.assertEqual(notifications.mapped("notification_type"), ["inbox"])
        self.assertFalse(self._mails(message))

    def test_no_out_of_office_reply(self):
        self.user_email.write(
            {
                "out_of_office_from": fields.Datetime.now() - timedelta(days=1),
                "out_of_office_to": fields.Datetime.now() + timedelta(days=1),
                "out_of_office_message": "<p>Away</p>",
            }
        )
        draft = self._open_draft()
        # The out-of-office reply goes to the author of the notified message.
        self._post(
            draft,
            "mail.mt_comment",
            partner_ids=[self.user_email.partner_id.id],
            author_id=self.user_b.partner_id.id,
        )
        self.assertFalse(
            self.env["mail.message"]
            .sudo()
            .search_count(
                [
                    ("model", "=", "mail.conversation.draft"),
                    ("res_id", "=", draft.id),
                    ("message_type", "=", "out_of_office"),
                ]
            )
        )

    def test_opt_out_keeps_externals_excluded(self):
        self.rule.write({"active": False})
        self.assertFalse(self.Draft._notification_scope_applies())
        draft = self._open_draft()
        message = self._post(
            draft,
            "mail.mt_comment",
            partner_ids=[self.partner_p.id, self.user_email.partner_id.id],
        )
        recipients = self._notifications(message).res_partner_id
        self.assertNotIn(self.partner_p, recipients)
        self.assertFalse(
            self._mails(message).filtered(lambda m: self.partner_p in m.recipient_ids)
        )
        draft.message_subscribe([self.partner_p.id])
        self.assertNotIn(self.partner_p, draft.message_partner_ids)
        # Without the rule the email-preference user is emailed again,
        # which shows the rule is what changes the behaviour.
        self.assertIn(self.user_email.partner_id, recipients)
        self.assertTrue(self._mails(message))
