from odoo.tests import tagged

from .common import CompanySignatureCommon


@tagged("post_install", "-at_install")
class TestCompanySignatureMail(CompanySignatureCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.external = cls.env["res.partner"].create(
            {"name": "Sig External", "email": "sig.external@example.com"}
        )
        cls.record = cls.env["res.partner"].create({"name": "Sig Thread"})

    def _post(self, **kwargs):
        with self.mock_mail_gateway():
            self.record.with_user(self.u_full).message_post(
                body="Bonjour",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                partner_ids=self.external.ids,
                **kwargs,
            )
            self.env.flush_all()
        mails = self._new_mails.filtered(
            lambda m: self.external in m.recipient_ids
        )
        self.assertEqual(len(mails), 1)
        return mails.body_html

    def test_chatter_email_has_signature_once(self):
        self._enable()
        body = self._post()
        self.assertEqual(body.count("514-555-0100 poste 12"), 1)

    def test_chatter_email_without_signature_flag(self):
        self._enable()
        body = self._post(email_add_signature=False)
        self.assertNotIn("514-555-0100", body)

    def test_policy_off_send_unchanged(self):
        body = self._post()
        self.assertEqual(body.count("Perso"), 1)
        self.assertNotIn("514-555-0100", body)

    def test_responsible_signature_layout_uses_generated_signature(self):
        self._enable()
        self.record.user_id = self.u_full
        body = self._post(
            email_layout_xmlid="mail.mail_notification_layout_with_responsible_signature"
        )
        self.assertIn("514-555-0100 poste 12", body)
