"""Confidentiality of the evaluation (read AS each user, never via sudo).

Acceptance criteria:
- The employee never reads the stored manager/calibrated grades, remarks or
  calibration notes (AccessError), and the per-user values stay empty until the
  manager shares the evaluation at the meeting; calibration notes are never shown.
- The manager does not see the self-evaluation before it is submitted, then does.
- A colleague cannot read another employee's evaluation.
- The employee cannot move the steps by writing fields, nor write manager grades;
  the manager cannot write the employee's grades.
- The calibration group reads the campaign's evaluations only once the campaign is in
  calibration, and only during calibration can adjust a grade.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import CampaignCase


@tagged("post_install", "-at_install")
class TestAccess(CampaignCase):
    def test_employee_never_reads_manager_side_before_share(self):
        appraisal = self.run_to_calibration(self_grade=3, manager_grade=2)
        line_emp = appraisal.campaign_line_ids[:1].with_user(self.employee_user)
        for fname in ("manager_grade", "calibrated_grade", "manager_remarks", "calibration_note",
                      "final_grade"):
            with self.assertRaises(AccessError), mute_logger("odoo.models"):
                line_emp.read([fname])
        self.assertEqual(line_emp.manager_grade_ui, 0)
        self.assertEqual(line_emp.final_grade_ui, 0)
        self.assertEqual(line_emp.employee_grade_ui, 3)
        with self.assertRaises(AccessError), mute_logger("odoo.models"):
            appraisal.with_user(self.employee_user).read(["score_final_total"])
        emp_view = appraisal.with_user(self.employee_user)
        self.assertEqual(emp_view.ui_final_total, 0)
        self.assertFalse(emp_view.ui_band_final_id)
        self.assertEqual(emp_view.ui_self_total, 3 * self.n_criteria)

    def test_manager_sees_self_eval_only_after_submit(self):
        appraisal = self.launch()
        self.set_self(appraisal, [4] * self.n_criteria)
        line_mgr = appraisal.campaign_line_ids[:1].with_user(self.manager_user)
        self.assertEqual(line_mgr.employee_grade_ui, 0)
        with self.assertRaises(AccessError), mute_logger("odoo.models"):
            line_mgr.read(["employee_grade"])
        appraisal.with_user(self.employee_user).action_campaign_submit_self()
        line_mgr.invalidate_recordset()
        self.assertEqual(line_mgr.employee_grade_ui, 4)
        self.assertEqual(appraisal.with_user(self.manager_user).ui_self_total, 4 * self.n_criteria)

    def test_colleague_cannot_read(self):
        appraisal = self.launch()
        with self.assertRaises(AccessError), mute_logger("odoo.addons.base.models.ir_rule"):
            appraisal.campaign_line_ids.with_user(self.colleague_user).read(["employee_grade_ui"])
        with self.assertRaises(AccessError), mute_logger("odoo.addons.base.models.ir_rule"):
            appraisal.with_user(self.colleague_user).read(["campaign_step"])

    def test_employee_cannot_force_steps_or_manager_grades(self):
        appraisal = self.launch()
        emp = appraisal.with_user(self.employee_user)
        for vals in ({"campaign_step": "closed"}, {"campaign_shared": True},
                     {"employee_ack_date": "2026-01-01 00:00:00"}):
            with self.assertRaises(AccessError):
                emp.write(vals)
        line = appraisal.campaign_line_ids[:1]
        with self.assertRaises(AccessError):
            line.with_user(self.employee_user).write({"manager_grade_ui": 4})
        with self.assertRaises(AccessError):
            line.with_user(self.employee_user).write({"calibrated_grade": 4, "calibration_note": "x"})
        with self.assertRaises(AccessError), mute_logger("odoo.models"):
            line.with_user(self.employee_user).write({"manager_grade": 4})
        # manager cannot grade in the employee's place
        with self.assertRaises(AccessError):
            line.with_user(self.manager_user).write({"employee_grade_ui": 1})
        # the employee cannot grade after submitting
        self.set_self(appraisal, [3] * self.n_criteria)
        emp.action_campaign_submit_self()
        with self.assertRaises(AccessError):
            line.with_user(self.employee_user).write({"employee_grade_ui": 4})

    def test_calibration_group_scope(self):
        # a director outside the employee's reporting line
        self.manager.parent_id = False
        appraisal = self.run_to_calibration()
        lines = appraisal.campaign_line_ids.with_user(self.director_user)
        with self.assertRaises(AccessError), mute_logger("odoo.addons.base.models.ir_rule"):
            lines.read(["manager_grade"])
        self.campaign.with_user(self.hr_user).action_start_calibration()
        lines.invalidate_recordset()
        self.assertEqual(lines[:1].manager_grade, 3)
        # the board's m2o columns resolve for a director without HR rights
        self.assertEqual(lines[:1].employee_id.display_name, "Test Employee Alpha")
        self.assertTrue(appraisal.with_user(self.director_user).campaign_can_see_manager)
        lines[:1].write({"calibrated_grade": 4, "calibration_note": "Consistent with peers"})
        self.campaign.with_user(self.hr_user).action_close_calibration()
        with self.assertRaises(UserError):
            lines[:1].write({"calibrated_grade": 2, "calibration_note": "too late"})

    def test_calibrator_cannot_calibrate_own(self):
        self.manager.parent_id = False
        self.employee.parent_id = self.manager
        # the director is evaluated too
        self.director.parent_id = self.manager
        self.campaign.employee_ids = [(4, self.director.id)]
        self.run_to_calibration()
        own = self.campaign.appraisal_ids.filtered(lambda a: a.employee_id == self.director)
        self.set_self(own, [3] * self.n_criteria, user=self.director_user)
        own.with_user(self.director_user).action_campaign_submit_self()
        self.set_manager(own, [3] * self.n_criteria)
        own.with_user(self.manager_user).action_campaign_submit_manager()
        self.campaign.with_user(self.hr_user).action_start_calibration()
        with self.assertRaises(AccessError):
            own.campaign_line_ids[:1].with_user(self.director_user).write(
                {"calibrated_grade": 4, "calibration_note": "self-serving"})
