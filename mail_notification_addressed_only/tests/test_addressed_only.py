"""Acceptance criteria (generic mechanism, on ``res.partner`` as the thread):

1. Inert by default: with no rule, stock notification behaviour.
2. Listed model: an unaddressed internal email-preference follower gets an
   inbox notification and no email.
3. Addressed internal users (partner_ids, composer Cc/Bcc) still get email.
4. External followers and bare ``outgoing_email_to`` addresses are unchanged.
5. Assignment-style ``message_notify`` still emails; later unaddressed posts
   do not.
6. Settings toggle: removing archives the rule and restores stock behaviour,
   re-adding turns it back on; nothing else is affected.
7. While a test suite runs, the mechanism stays inert unless the test opts in
   through the ``test_mail_notification_addressed_only`` context key, so other
   modules' suites keep their stock expectations.
"""

from odoo.tests import Form, tagged

from .common import AddressedOnlyCommon


@tagged("post_install", "-at_install")
class TestAddressedOnly(AddressedOnlyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.record = cls.env["res.partner"].create({"name": "Addressed Thread"})
        cls.followers = (
            cls.external
            | cls.internal_follower.partner_id
            | cls.internal_inbox.partner_id
        )
        cls._follow(cls.record, cls.followers)

    def _set_models(self, *model_names):
        with Form(self.env["res.config.settings"]) as form:
            form.addressed_only_model_ids.clear()
            for name in model_names:
                form.addressed_only_model_ids.add(self.env["ir.model"]._get(name))
        form.save().execute()

    def test_01_inert_by_default(self):
        message = self._post(self.record)
        self.assertTrue(self._mails_to(self.internal_follower.partner_id))
        self.assertFalse(self._inbox_notif(message, self.internal_follower.partner_id))

    def test_02_unaddressed_internal_follower_inbox_only(self):
        self._list_model("res.partner")
        message = self._post(self.record)
        partner = self.internal_follower.partner_id
        self.assertFalse(self._mails_to(partner))
        self.assertTrue(self._inbox_notif(message, partner))
        # "Handle in Odoo" users are unaffected, still have their inbox entry
        self.assertTrue(self._inbox_notif(message, self.internal_inbox.partner_id))

    def test_03_addressed_internal_still_emailed(self):
        self._list_model("res.partner")
        other = self.internal_other.partner_id
        self._post(self.record, partner_ids=other.ids)
        self.assertTrue(self._mails_to(other))
        # follower AND addressed counts as addressed
        follower = self.internal_follower.partner_id
        self._post(self.record, partner_ids=follower.ids)
        self.assertTrue(self._mails_to(follower))

    def test_04_cc_bcc_context_counts_as_addressed(self):
        self._list_model("res.partner")
        follower = self.internal_follower.partner_id
        self._post(
            self.record.with_context(is_from_composer=True, partner_cc_ids=follower)
        )
        self.assertTrue(self._mails_to(follower))

    def test_05_externals_unchanged(self):
        self._list_model("res.partner")
        self._post(self.record, outgoing_email_to="bare@example.com")
        self.assertTrue(self._mails_to(self.external))
        self.assertTrue(
            self.env["mail.mail"].search([("email_to", "ilike", "bare@example.com")])
        )

    def test_06_assignment_notify_then_followup(self):
        self._list_model("res.partner")
        assignee = self.internal_other.partner_id
        with self.mock_mail_gateway():
            self.record.with_user(self.user_admin).message_notify(
                partner_ids=assignee.ids,
                body="assigned",
                subject="Assigned",
                subtype_xmlid="mail.mt_note",
            )
            self.env.flush_all()
        self.assertTrue(self._mails_to(assignee))
        self.env["mail.mail"].search([]).unlink()
        self._follow(self.record, assignee)
        message = self._post(self.record)
        self.assertFalse(self._mails_to(assignee))
        self.assertTrue(self._inbox_notif(message, assignee))

    def test_07_settings_toggle_archives_and_restores(self):
        follower = self.internal_follower.partner_id
        self._set_models("res.partner")
        self._post(self.record)
        self.assertFalse(self._mails_to(follower))
        Rule = self.env["mail.addressed.only.rule"].with_context(active_test=False)
        rule = Rule.search([("model", "=", "res.partner")])
        self.assertEqual(len(rule), 1)
        self._set_models()
        self.assertEqual(Rule.search([("model", "=", "res.partner")]), rule)
        self.assertFalse(rule.active)
        self._post(self.record)
        self.assertTrue(self._mails_to(follower))
        self._set_models("res.partner")
        self.assertTrue(rule.active)

    def test_08_discuss_channel_never_applies(self):
        self.assertFalse(self.env["discuss.channel"]._addressed_only_applies())

    def test_09_other_suites_see_stock_behaviour(self):
        """Without the opt-in context key, a running test suite of another
        module keeps stock behaviour even on a listed model."""
        self._list_model("res.partner")
        record = self.record.with_context(test_mail_notification_addressed_only=False)
        self.assertFalse(record._addressed_only_applies())
        message = self._post(record)
        partner = self.internal_follower.partner_id
        self.assertTrue(self._mails_to(partner))
        self.assertFalse(self._inbox_notif(message, partner))
