"""Acceptance criteria (generic mechanism, on ``res.partner`` as the thread):

1. Inert by default: with no rule and no flag, stock notification behaviour.
2. Opt-in through Settings: externals and bare emails are never notified,
   internal email users get an inbox notification instead.
3. Opt-out archives the rule (never deletes) and restores stock behaviour;
   re-adding reactivates the same row.
4. The "all models" flag applies everywhere except discuss channels and
   abstract models.
5. ``mail.mt_comment`` is never modified.
"""

from odoo.tests import Form, tagged
from odoo.addons.mail.tests.common import MailCommon


@tagged("post_install", "-at_install")
class TestNotificationScope(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_email_user = cls.env["res.users"].create(
            {
                "name": "Scope Internal Email",
                "login": "scope_internal_email",
                "email": "scope.internal@example.com",
                "notification_type": "email",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.external = cls.env["res.partner"].create(
            {"name": "Scope External", "email": "scope.external@example.com"}
        )
        cls.record = cls.env["res.partner"].create({"name": "Scope Thread"})
        cls.record.message_subscribe(
            partner_ids=(cls.external | cls.internal_email_user.partner_id).ids,
            subtype_ids=[cls.env.ref("mail.mt_comment").id],
        )

    def _post(self):
        with self.mock_mail_gateway():
            message = self.record.with_user(self.user_employee).message_post(
                body="hello",
                subtype_xmlid="mail.mt_comment",
                message_type="comment",
            )
            self.env.flush_all()
        return message

    def _mails_to(self, partner):
        return self.env["mail.mail"].search(
            [("recipient_ids", "in", partner.ids)]
        ) | self.env["mail.mail"].search([("email_to", "ilike", partner.email)])

    def _notifications(self, message):
        return self.env["mail.notification"].search(
            [("mail_message_id", "=", message.id)]
        )

    def _opt_in(self):
        with Form(self.env["res.config.settings"]) as form:
            form.notification_scope_model_ids.add(
                self.env["ir.model"]._get("res.partner")
            )
        form.save().execute()

    def test_01_inert_by_default(self):
        message = self._post()
        self.assertTrue(
            self._notifications(message).filtered(
                lambda n: n.res_partner_id == self.external
            )
        )
        self.assertTrue(self._mails_to(self.external))
        self.assertTrue(self._mails_to(self.internal_email_user.partner_id))

    def test_02_opt_in_through_settings(self):
        self._opt_in()
        message = self._post()
        self.assertFalse(self._mails_to(self.external))
        self.assertFalse(self._mails_to(self.internal_email_user.partner_id))
        notifs = self._notifications(message)
        internal_notif = notifs.filtered(
            lambda n: n.res_partner_id == self.internal_email_user.partner_id
        )
        self.assertEqual(internal_notif.notification_type, "inbox")
        self.assertFalse(notifs.filtered(lambda n: n.res_partner_id == self.external))
        with self.mock_mail_gateway():
            self.record.message_post(
                body="bare",
                subtype_xmlid="mail.mt_comment",
                outgoing_email_to="bare@example.com",
            )
            self.env.flush_all()
        self.assertFalse(
            self.env["mail.mail"].search([("email_to", "ilike", "bare@example.com")])
        )

    def test_03_opt_out_archives_and_restores(self):
        self._opt_in()
        Rule = self.env["mail.notification.scope"].with_context(active_test=False)
        rule = Rule.search([("model", "=", "res.partner")])
        self.assertEqual(len(rule), 1)
        with Form(self.env["res.config.settings"]) as form:
            form.notification_scope_model_ids.clear()
        form.save().execute()
        self.assertEqual(Rule.search([("model", "=", "res.partner")]), rule)
        self.assertFalse(rule.active)
        self._post()
        self.assertTrue(self._mails_to(self.external))
        self._opt_in()
        self.assertEqual(Rule.search_count([("model", "=", "res.partner")]), 1)
        self.assertTrue(rule.active)

    def test_04_all_models_flag_and_exclusions(self):
        self.assertFalse(self.env["res.partner"]._notification_scope_applies())
        with Form(self.env["res.config.settings"]) as form:
            form.notification_scope_all_models = True
        form.save().execute()
        self.assertTrue(self.env["res.partner"]._notification_scope_applies())
        self.assertFalse(self.env["discuss.channel"]._notification_scope_applies())
        self.assertFalse(self.env["mail.thread"]._notification_scope_applies())
        with Form(self.env["res.config.settings"]) as form:
            form.notification_scope_all_models = False
        form.save().execute()
        self.assertFalse(self.env["res.partner"]._notification_scope_applies())

    def test_05_mt_comment_untouched(self):
        subtype = self.env.ref("mail.mt_comment")
        before = (subtype.internal, subtype.default)
        self._opt_in()
        subtype.invalidate_recordset()
        self.assertEqual((subtype.internal, subtype.default), before)
