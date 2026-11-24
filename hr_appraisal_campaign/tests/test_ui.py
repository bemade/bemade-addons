"""Browser checks of the word-picture widget.

Acceptance criteria:
- (Hoot) clicking a word picture sets the grade of that criterion and highlights it.
- (Tour) the employee grades every criterion by clicking word pictures and submits the
  self-evaluation to the manager.
These run a real browser; they prove the widget mounts and saves, not the full UX —
the click-through at review remains required.
"""

from odoo.tests import HttpCase, tagged

from .common import CampaignCase


@tagged("post_install", "-at_install")
class TestWordPictureTour(HttpCase, CampaignCase):
    def test_self_evaluation_tour(self):
        appraisal = self.launch()
        self.employee_user.lang = "en_US"
        self.start_tour(
            f"/odoo/action-hr_appraisal.open_view_hr_appraisal_tree/{appraisal.id}",
            "hr_appraisal_campaign_self_evaluation_tour",
            login="hac_emp",
        )
        self.assertEqual(appraisal.campaign_step, "manager_eval")
        self.assertEqual(appraisal.campaign_line_ids.sudo().mapped("employee_grade"), [3] * self.n_criteria)


@tagged("post_install", "-at_install")
class TestWordPictureHoot(HttpCase):
    def test_word_picture_hoot(self):
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=desktop&timeout=15000&filter=campaign_word_picture",
            "", "", login="admin", timeout=900,
            success_signal="[HOOT] Test suite succeeded",
        )
