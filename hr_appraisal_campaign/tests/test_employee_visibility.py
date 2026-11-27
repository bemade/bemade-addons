"""The employee sees the evaluation in Odoo only AFTER the meeting.

Acceptance criteria:
- Until the manager records « Meeting held — share with the employee », the employee
  reads nothing of the manager's / final evaluation in Odoo: no grade, remark, score or
  band on the lines or the form, no final column in the printout, nothing in the
  chatter, the to-dos or the e-mails of the evaluation.
- « Meeting held » is only possible at the meeting step, by the evaluator or HR; it posts
  a note (no evaluation content) and gives the employee the « read and acknowledge »
  to-do.
- After it, the employee sees the final grades and the remarks as they stand — including
  a remark amended during the meeting — then acknowledges, which freezes the remarks.
- The button and its confirmation say it is done after the meeting.
"""

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import CampaignCase

SECRET = "MANAGER-REMARK-SECRET"


@tagged("post_install", "-at_install")
class TestEmployeeVisibility(CampaignCase):
    def _report_html(self, appraisal, user):
        return self.env["ir.actions.report"].with_user(user)._render_qweb_html(
            "hr_appraisal_campaign.report_campaign_appraisal", appraisal.ids,
            data={"report_lang": "en_US"})[0].decode()

    def _employee_sees_nothing(self, appraisal, stage):
        emp = appraisal.with_user(self.employee_user)
        emp.invalidate_recordset()
        self.assertFalse(emp.campaign_can_see_manager, stage)
        self.assertEqual(emp.ui_final_total, 0, stage)
        self.assertFalse(emp.ui_band_final_id, stage)
        results = str(emp.campaign_results_html or "")
        self.assertIn("Self-evaluation", results, stage)
        self.assertNotIn("Final evaluation", results, stage)
        for line in emp.campaign_line_ids:
            self.assertEqual(line.manager_grade_ui, 0, stage)
            self.assertEqual(line.final_grade_ui, 0, stage)
            self.assertFalse(line.manager_remarks_ui, stage)
        html = self._report_html(appraisal, self.employee_user)
        self.assertNotIn(SECRET, html, stage)
        self.assertNotIn("Final evaluation", html, stage)
        # chatter, to-dos and mails of the evaluation
        messages = self.env["mail.message"].with_user(self.employee_user).search(
            [("model", "=", "hr.appraisal"), ("res_id", "=", appraisal.id)])
        self.assertNotIn(SECRET, " ".join(str(m.body) for m in messages), stage)
        activities = appraisal.sudo().activity_ids
        self.assertNotIn(SECRET, " ".join(str(a.note or "") + (a.summary or "") for a in activities))
        mails = self.env["mail.mail"].sudo().search([])
        self.assertNotIn(SECRET, " ".join(str(m.body_html or "") for m in mails), stage)

    def test_nothing_visible_before_meeting_held(self):
        appraisal = self.launch()
        self.set_self(appraisal, [3] * self.n_criteria)
        appraisal.with_user(self.employee_user).action_campaign_submit_self()
        first = appraisal.campaign_line_ids[0]
        first.with_user(self.manager_user).write({"manager_remarks_ui": SECRET})
        self.set_manager(appraisal, [2] * self.n_criteria)
        self._employee_sees_nothing(appraisal, "manager_eval")
        appraisal.with_user(self.manager_user).action_campaign_submit_manager()
        self._employee_sees_nothing(appraisal, "calibration (waiting)")
        self.campaign.with_user(self.hr_user).action_start_calibration()
        self._employee_sees_nothing(appraisal, "calibration")
        self.campaign.with_user(self.hr_user).action_close_calibration()
        self.assertEqual(appraisal.campaign_step, "meeting")
        self._employee_sees_nothing(appraisal, "meeting, not held yet")
        # the employee cannot acknowledge something not shared
        with self.assertRaises(UserError):
            appraisal.with_user(self.employee_user).action_campaign_acknowledge()

    def test_meeting_held_only_at_meeting_step_by_evaluator(self):
        appraisal = self.run_to_calibration()
        with self.assertRaises(UserError):
            appraisal.with_user(self.manager_user).action_campaign_share()
        self.campaign.with_user(self.hr_user).action_start_calibration()
        self.campaign.with_user(self.hr_user).action_close_calibration()
        for user in (self.employee_user, self.director_user):
            with self.assertRaises(AccessError):
                appraisal.with_user(user).action_campaign_share()
        appraisal.with_user(self.manager_user).action_campaign_share()
        self.assertTrue(appraisal.campaign_shared)
        note = appraisal.message_ids.filtered(lambda m: "Meeting held" in str(m.body))
        self.assertTrue(note, "a note records the meeting")
        self.assertTrue(appraisal.activity_ids.filtered(lambda a: a.user_id == self.employee_user))

    def test_after_meeting_held_employee_sees_amended_remarks_then_acknowledges(self):
        appraisal = self.run_to_calibration(self_grade=3, manager_grade=2)
        self.campaign.with_user(self.hr_user).action_start_calibration()
        self.campaign.with_user(self.hr_user).action_close_calibration()
        first = appraisal.campaign_line_ids[0]
        # amended with the employee during the meeting, before « Meeting held »
        first.with_user(self.manager_user).write({"manager_remarks_ui": "Amended together"})
        appraisal.with_user(self.manager_user).action_campaign_share()
        emp_line = first.with_user(self.employee_user)
        self.assertEqual(emp_line.manager_remarks_ui, "Amended together")
        self.assertEqual(emp_line.final_grade_ui, 2)
        # still amendable after « Meeting held » until the acknowledgement
        first.with_user(self.manager_user).write({"manager_remarks_ui": "Amended after the meeting"})
        emp_line.invalidate_recordset()
        self.assertEqual(emp_line.manager_remarks_ui, "Amended after the meeting")
        html = self._report_html(appraisal, self.employee_user)
        self.assertIn("Amended after the meeting", html)
        emp = appraisal.with_user(self.employee_user)
        emp.invalidate_recordset()
        self.assertIn("Final evaluation", str(emp.campaign_results_html))
        appraisal.with_user(self.employee_user).action_campaign_acknowledge()
        with self.assertRaises(AccessError):
            first.with_user(self.manager_user).write({"manager_remarks_ui": "Too late"})

    def test_button_says_meeting_held(self):
        arch = self.env["hr.appraisal"].with_user(self.manager_user).get_views(
            [(False, "form")])["views"]["form"]["arch"]
        button = etree.fromstring(arch).xpath("//button[@name='action_campaign_share']")[0]
        self.assertEqual(button.get("string"), "Meeting held — share with the employee")
        self.assertIn("after the meeting", button.get("confirm"))
        self.assertIn("campaign_step != 'meeting'", button.get("invisible"))
