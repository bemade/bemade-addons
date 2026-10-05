from odoo.tests import HttpCase, tagged

from .common import TEMPLATE_A

PHONE = "514-555-0100 poste 12"


@tagged("post_install", "-at_install")
class TestCompanySignatureUI(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        company.company_signature_template = TEMPLATE_A
        cls.user = cls.env["res.users"].create(
            {
                "name": "Sig Tour",
                "login": "sig_tour",
                "password": "sig_tour",
                "email": "sig_tour@example.com",
                "company_id": company.id,
                "company_ids": [(6, 0, company.ids)],
                "group_ids": [(6, 0, cls.env.ref("base.group_user").ids)],
            }
        )
        cls.env["hr.employee"].sudo().search([("user_id", "=", cls.user.id)]).unlink()
        cls.env["hr.employee"].sudo().create(
            {
                "name": "Sig Tour",
                "user_id": cls.user.id,
                "company_id": company.id,
                "job_title": "Intégrateur",
                "work_phone": PHONE,
            }
        )
        company.company_signature_enforced = True
        cls.partner = cls.env["res.partner"].create(
            {"name": "Client Sig", "email": "client.sig@example.com"}
        )

    def _tour(self, name):
        self.start_tour(
            "/odoo/res.partner/%s" % self.partner.id, name, login="sig_tour"
        )

    def _mails(self, message):
        return self.env["mail.mail"].search([("mail_message_id", "=", message.id)])

    def _message(self, text):
        return self.env["mail.message"].search(
            [
                ("model", "=", "res.partner"),
                ("res_id", "=", self.partner.id),
                ("body", "ilike", text),
            ],
            limit=1,
        )

    def test_inline_send(self):
        self._tour("mail_company_signature_inline_send")
        message = self._message("Hello inline")
        self.assertTrue(message.email_add_signature)
        mails = self._mails(message)
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.body_html.count(PHONE), 1)

    def test_inline_remove(self):
        self._tour("mail_company_signature_inline_remove")
        message = self._message("No sig")
        self.assertFalse(message.email_add_signature)
        self.assertNotIn("514-555-0100", self._mails(message).body_html)

    def test_log_note(self):
        self._tour("mail_company_signature_log_note")
        message = self._message("Internal")
        self.assertFalse(self._mails(message))
        self.assertNotIn("514-555-0100", message.body)

    def test_full_composer(self):
        self._tour("mail_company_signature_full_composer")
        mails = self.env["mail.mail"].search(
            [("model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
        )
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.body_html.count(PHONE), 1)
