"""Evaluation PDF.

Acceptance criteria:
- The evaluation renders in French and in English (criteria and word pictures in the
  chosen language).
- Printed by the employee before the share, it shows no manager/final grade; the
  calibration notes never appear.
"""

from markupsafe import escape

from odoo.tests import tagged

from .common import CampaignCase


@tagged("post_install", "-at_install")
class TestReport(CampaignCase):
    def _html(self, appraisal, lang, user=None):
        report = self.env["ir.actions.report"]
        if user:
            report = report.with_user(user)
        return report._render_qweb_html(
            "hr_appraisal_campaign.report_campaign_appraisal", appraisal.ids,
            data={"report_lang": lang})[0].decode()

    def test_render_fr_en_and_confidentiality(self):
        appraisal = self.run_to_calibration(self_grade=3, manager_grade=2)
        self.campaign.with_user(self.hr_user).action_start_calibration()
        appraisal.campaign_line_ids[:1].with_user(self.director_user).write(
            {"calibrated_grade": 3, "calibration_note": "SECRET-CALIBRATION-NOTE"})
        appraisal.campaign_line_ids[:1].sudo().manager_remarks = "VISIBLE-REMARK"
        first = appraisal.campaign_line_ids[:1]
        html_fr = self._html(appraisal, "fr_FR", self.hr_user)
        html_en = self._html(appraisal, "en_US", self.hr_user)
        self.assertIn(str(escape(first.with_context(lang="fr_FR").name)), html_fr)
        self.assertIn("3 – Moyen", html_fr)
        self.assertNotIn("3 – 3", html_fr)
        self.assertIn(str(escape(first.with_context(lang="en_US").name)), html_en)
        self.assertIn("3 – Medium", html_en)
        self.assertNotIn("3 – 3", html_en)
        self.assertNotIn("SECRET-CALIBRATION-NOTE", html_fr + html_en)
        self.assertIn("VISIBLE-REMARK", html_en)
        # the employee printing before the share sees only their own side
        html_emp = self._html(appraisal, "en_US", self.employee_user)
        self.assertNotIn("VISIBLE-REMARK", html_emp)
        self.assertNotIn("2 – Low", html_emp)
        self.assertIn("3 – Medium", html_emp)
