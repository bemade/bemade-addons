"""Use case: a temporary company notice under every enforced signature.

Acceptance criteria
-------------------
* Per company (Settings > Emails), an administrator sets a "Company notice"
  (rich text) and an optional "Show until" date.
* ``{{company_notice}}`` renders the notice as HTML (formatting kept, not
  escaped) in the signature of every enforced user of the company; never in
  another company's signatures.
* A paragraph holding only ``{{company_notice}}`` does not nest the notice's
  own paragraphs inside a ``<p>``.
* Without a notice (empty, or after its "Show until" date), the paragraph of
  ``{{company_notice}}`` is removed (existing empty-line rule).
* The notice is shown up to and including its "Show until" day.
* A daily scheduled action clears the notice and its date once the date has
  passed, which regenerates the signatures without it; undated and future
  notices are left alone.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import Form, freeze_time, tagged

from .common import CompanySignatureCommon

TEMPLATE = "<p>{{name}}</p><p>{{company_name}}</p><p>{{company_notice}}</p>"
NOTICE = "<p>Closed for inventory on <strong>Friday</strong>.</p>"
NOTICE_TEXT = "Closed for inventory on <strong>Friday</strong>."


@tagged("post_install", "-at_install")
class TestCompanyNotice(CompanySignatureCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a.sudo().company_signature_template = TEMPLATE
        cls.company_b.sudo().company_signature_template = TEMPLATE
        cls.cron = cls.env.ref("mail_company_signature.ir_cron_expire_company_notice")

    def setUp(self):
        super().setUp()
        self._enable()
        self._enable(self.company_b)
        self.enforced_a = self.u_full | self.u_nomobile

    def _run_cron(self):
        self.assertTrue(self.cron.active)
        self.assertIn("_cron_expire_company_signature_notice", self.cron.code)
        self.env["res.company"]._cron_expire_company_signature_notice()

    def test_notice_from_settings(self):
        form = Form(self.env["res.config.settings"].with_company(self.company_a))
        form.company_signature_notice = NOTICE
        form.company_signature_notice_until = fields.Date.today() + timedelta(days=2)
        form.save().execute()
        self.assertEqual(
            self.company_a.sudo().company_signature_notice_until,
            fields.Date.today() + timedelta(days=2),
        )
        for user in self.enforced_a:
            sig = user.signature
            self.assertIn(NOTICE_TEXT, sig)
            self.assertGreater(sig.find(NOTICE_TEXT), sig.find(self.company_a.name))
        self.assertNotIn("inventory", self.u_b.signature)

    def test_no_nested_paragraph(self):
        self.company_a.sudo().company_signature_notice = NOTICE
        sig = self.u_full.signature
        self.assertNotIn("<p><p>", sig)
        self.assertIn(NOTICE_TEXT, sig)

    def test_empty_notice_drops_paragraph(self):
        sig = self.u_full.signature
        self.assertNotIn("{{", sig)
        self.assertNotIn("<p></p>", sig)
        self.assertTrue(sig.rstrip().endswith("%s</p>" % self.company_a.name), sig)
        self.company_a.sudo().company_signature_notice = "<p><br></p>"
        self.assertNotIn("<br>", self.u_full.signature)

    def test_until_today_shown_then_cron_removes(self):
        today = fields.Date.today()
        self.company_a.sudo().write(
            {
                "company_signature_notice": NOTICE,
                "company_signature_notice_until": today,
            }
        )
        self.assertIn(NOTICE_TEXT, self.u_full.signature)
        self._run_cron()
        self.assertIn(NOTICE_TEXT, self.u_full.signature)
        with freeze_time(today + timedelta(days=1)):
            self._run_cron()
            company = self.company_a.sudo()
            self.assertFalse(company.company_signature_notice)
            self.assertFalse(company.company_signature_notice_until)
            for user in self.enforced_a:
                self.assertNotIn("inventory", user.signature)

    def test_expired_notice_not_rendered(self):
        self.company_a.sudo().write(
            {
                "company_signature_notice": NOTICE,
                "company_signature_notice_until": fields.Date.today()
                - timedelta(days=1),
            }
        )
        self.assertNotIn("inventory", self.u_full.signature)

    def test_cron_keeps_undated_and_future(self):
        self.company_a.sudo().company_signature_notice = NOTICE
        self.company_b.sudo().write(
            {
                "company_signature_notice": NOTICE,
                "company_signature_notice_until": fields.Date.today()
                + timedelta(days=3),
            }
        )
        self._run_cron()
        self.assertIn("inventory", self.company_a.sudo().company_signature_notice)
        self.assertIn("inventory", self.company_b.sudo().company_signature_notice)
        self.assertIn(NOTICE_TEXT, self.u_full.signature)
        self.assertIn(NOTICE_TEXT, self.u_b.signature)
