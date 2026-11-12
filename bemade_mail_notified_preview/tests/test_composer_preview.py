"""The full composer shows the followers line under the recipients.

Acceptance criteria:

1.  Opening the composer on one record in comment mode ("Send message") shows
    the line computed from the record's followers.
2.  Adding a follower to the recipients (To) removes them from the line, live
    (recomputed on ``partner_ids``).
3.  No line on a log note (``subtype_is_log``), nor when composing on several
    records (batch / mass mail).
4.  When the OCA module ``mail_composer_cc_bcc`` is installed, partners in Cc
    or Bcc are left out of the line too, and the line sits after the Cc/Bcc
    rows (checked only when that module is installed).
5.  Sending from the composer notifies exactly the same people as before the
    module: the line is display only.
"""

from lxml import etree

from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestComposerPreview(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.sender = new_test_user(
            cls.env,
            login="composer_sender",
            name="Sample Sender",
            email="sender@example.com",
            groups="base.group_user,base.group_partner_manager",
        )
        cls.user_inbox = new_test_user(
            cls.env,
            login="composer_inbox",
            name="Alice Inbox",
            email="alice@example.com",
            notification_type="inbox",
        )
        Partner = cls.env["res.partner"]
        cls.contact = Partner.create({"name": "Carol Contact", "email": "carol@example.com"})
        cls.record = Partner.create({"name": "Sample Customer Co"})
        cls.other_record = Partner.create({"name": "Other Customer Co"})
        records = cls.record | cls.other_record
        records.message_unsubscribe(partner_ids=records.message_partner_ids.ids)
        records.message_subscribe(
            partner_ids=(cls.sender.partner_id | cls.user_inbox.partner_id | cls.contact).ids,
            subtype_ids=cls.env.ref("mail.mt_comment").ids,
        )

    def _composer_form(self, res_ids, **ctx):
        context = {
            "default_model": "res.partner",
            "default_res_ids": res_ids,
            "default_composition_mode": "comment",
            **ctx,
        }
        Composer = self.env["mail.compose.message"].with_user(self.sender)
        return Form(Composer.with_context(**context))

    def test_line_shown_and_recomputed_on_recipients(self):
        form = self._composer_form(self.record.ids)
        self.assertEqual(
            form.notified_followers_preview,
            "Also sent to followers: Carol Contact (email) · Alice Inbox (Odoo inbox)",
        )
        form.partner_ids.add(self.contact)
        self.assertEqual(
            form.notified_followers_preview,
            "Also sent to followers: Alice Inbox (Odoo inbox)",
        )
        form.partner_ids.add(self.user_inbox.partner_id)
        self.assertEqual(form.notified_followers_preview, "No followers will be notified")

    def test_no_line_on_log_note(self):
        form = self._composer_form(
            self.record.ids,
            default_subtype_id=self.env.ref("mail.mt_note").id,
        )
        self.assertTrue(form.subtype_is_log)
        self.assertFalse(form.notified_followers_preview)

    def test_no_line_on_batch(self):
        form = self._composer_form(
            (self.record | self.other_record).ids,
            default_composition_mode="mass_mail",
        )
        self.assertFalse(form.notified_followers_preview)

    def test_send_unchanged(self):
        form = self._composer_form(self.record.ids)
        form.body = "Synthetic body"
        form.subject = "Synthetic subject"
        composer = form.save()
        composer._action_send_mail()
        message = self.record.message_ids[:1]
        self.assertEqual(message.body, "<p>Synthetic body</p>")
        self.assertEqual(
            message.notification_ids.res_partner_id,
            self.user_inbox.partner_id | self.contact,
        )

    def test_line_is_after_recipient_rows(self):
        arch = self.env["mail.compose.message"].get_view(
            self.env.ref("mail.email_compose_message_wizard_form").id
        )["arch"]
        names = [node.get("name") for node in etree.fromstring(arch).iter("field")]
        line = names.index("notified_followers_preview")
        self.assertLess(line, names.index("subject"))
        for fname in ("partner_ids", "partner_cc_ids", "partner_bcc_ids"):
            if fname in names:
                self.assertGreater(line, len(names) - 1 - names[::-1].index(fname))

    def test_cc_bcc_excluded_when_installed(self):
        if "partner_cc_ids" not in self.env["mail.compose.message"]._fields:
            self.skipTest("mail_composer_cc_bcc is not installed")
        form = self._composer_form(self.record.ids)
        form.partner_cc_ids.add(self.contact)
        form.partner_bcc_ids.add(self.user_inbox.partner_id)
        self.assertEqual(form.notified_followers_preview, "No followers will be notified")
