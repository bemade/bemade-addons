"""Use case 4 — the fixed evaluation flow, end to end, on a 5-level scale.

Acceptance criteria:
- Self-evaluation → « Submit to my Manager » only once every criterion is graded; the
  employee's part locks and the evaluator gets a to-do.
- A grade outside the scale (0 excepted = not graded) is refused, e.g. 6 on a 5-level
  scale; the top level (5) is accepted.
- Manager evaluation → « Submit for Calibration » only when all graded; calibrated
  grades start equal to the manager's.
- Calibration: a calibrator's change needs a note and is logged (who, from → to); HR
  closes the calibration → meeting step, evaluator to-do.
- Meeting: the evaluator records « Meeting held — share » → the employee sees the
  final grades next to their own, never the calibration notes.
- Acknowledgement: employee « read and discussed » (user + time, optional comment) and
  evaluator validation → acknowledged; HR closes → locked, Odoo state done, PDF attached.
- The hook after the self-evaluation returns nothing by default.
- A campaign closes only when all its evaluations are closed.
"""

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import CampaignCase


@tagged("post_install", "-at_install")
class TestWorkflow(CampaignCase):
    def test_full_flow(self):
        self.campaign.alignment_gap = 2
        appraisal = self.launch()
        emp = appraisal.with_user(self.employee_user)
        mgr = appraisal.with_user(self.manager_user)
        n = self.n_criteria
        last = appraisal.campaign_line_ids[-1]

        # 1. self-evaluation
        with self.assertRaises(ValidationError):
            last.with_user(self.employee_user).write({"employee_grade_ui": 6})
        self.set_self(appraisal, [3] * (n - 1))
        with self.assertRaises(UserError):
            emp.action_campaign_submit_self()
        last.with_user(self.employee_user).write(
            {"employee_grade_ui": 5, "employee_examples_ui": "Trained two new colleagues"})
        self.assertTrue(emp.action_campaign_submit_self())
        self.assertEqual(appraisal.campaign_step, "manager_eval")
        self.assertEqual(appraisal.state, "2_pending")
        self.assertTrue(appraisal.activity_ids.filtered(lambda a: a.user_id == self.manager_user))
        self.assertFalse(appraisal.activity_ids.filtered(lambda a: a.user_id == self.employee_user))

        # 2. manager evaluation
        self.set_manager(appraisal, [3] * (n - 1))
        with self.assertRaises(UserError):
            mgr.action_campaign_submit_manager()
        last.with_user(self.manager_user).write(
            {"manager_grade_ui": 2, "manager_remarks_ui": "Punctuality to improve"})
        with self.assertRaises(AccessError):
            emp.action_campaign_submit_manager()
        mgr.action_campaign_submit_manager()
        self.assertEqual(appraisal.campaign_step, "calibration")
        self.assertEqual(appraisal.campaign_line_ids.sudo().mapped("calibrated_grade"),
                         [3] * (n - 1) + [2])

        # 3. calibration
        self.campaign.with_user(self.hr_user).action_start_calibration()
        line = last.with_user(self.director_user)
        with self.assertRaises(ValidationError):
            line.write({"calibrated_grade": 3})
        line.write({"calibrated_grade": 3, "calibration_note": "Aligned with team practice"})
        log = self.env["hr.appraisal.campaign.calibration.log"].search([("line_id", "=", line.id)])
        self.assertEqual((log.user_id, log.old_grade, log.new_grade), (self.director_user, 2, 3))
        with self.assertRaises(ValidationError):
            line.write({"calibrated_grade": 6, "calibration_note": "Off the scale"})
        self.campaign.with_user(self.hr_user).action_close_calibration()
        self.assertEqual(appraisal.campaign_step, "meeting")
        self.assertTrue(appraisal.activity_ids.filtered(lambda a: a.user_id == self.manager_user))

        # 4. meeting — nothing visible before « meeting held »
        emp_line = last.with_user(self.employee_user)
        self.assertEqual(emp_line.final_grade_ui, 0)
        with self.assertRaises(UserError):
            emp.action_campaign_acknowledge()
        mgr.action_campaign_share()
        emp_line.invalidate_recordset()
        self.assertEqual(emp_line.final_grade_ui, 3)
        self.assertEqual(emp_line.manager_remarks_ui, "Punctuality to improve")
        self.assertEqual(emp_line.employee_grade_ui, 5)
        with self.assertRaises(AccessError), mute_logger("odoo.models"):
            emp_line.read(["calibration_note"])
        emp.invalidate_recordset()
        self.assertEqual(emp.ui_final_total, 3 * n)
        self.assertEqual(emp.ui_self_total, 3 * (n - 1) + 5)
        self.assertEqual(emp.ui_aligned, "aligned")

        # 5. acknowledgement
        emp.write({"employee_ack_comment": "Fair discussion"})
        emp.action_campaign_acknowledge()
        self.assertEqual(appraisal.employee_ack_user_id, self.employee_user)
        self.assertTrue(appraisal.employee_ack_date)
        self.assertEqual(appraisal.campaign_step, "meeting")
        with self.assertRaises(AccessError):
            emp.action_campaign_validate()
        mgr.action_campaign_validate()
        self.assertEqual(appraisal.manager_validated_user_id, self.manager_user)
        self.assertEqual(appraisal.campaign_step, "acknowledged")

        # 6. HR close
        with self.assertRaises(AccessError):
            mgr.action_campaign_close()
        appraisal.with_user(self.hr_user).action_campaign_close()
        self.assertEqual(appraisal.campaign_step, "closed")
        self.assertEqual(appraisal.state, "3_done")
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", "hr.appraisal"), ("res_id", "=", appraisal.id)])
        self.assertEqual(len(attachment), 1)
        with self.assertRaises(UserError):
            appraisal.campaign_line_ids[:1].with_user(self.hr_user).write({"employee_grade": 1})

    def test_hook_default(self):
        appraisal = self.launch()
        self.assertFalse(appraisal._campaign_after_self_eval_steps())

    def test_campaign_close_requires_all_closed(self):
        self.run_to_calibration()
        self.campaign.with_user(self.hr_user).action_start_calibration()
        self.campaign.with_user(self.hr_user).action_close_calibration()
        with self.assertRaises(UserError):
            self.campaign.with_user(self.hr_user).action_close()
