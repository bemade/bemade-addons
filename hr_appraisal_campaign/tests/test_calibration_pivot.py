"""Calibration board = a pivot matrix.

Acceptance criteria:
- The Calibration Board opens on a pivot: one row per employee, one column per
  criterion in catalogue order (section sequence, then criterion sequence), the cell = the final (calibrated) grade.
- Grade measures aggregate with an average, never a sum, so a cell shows the grade
  itself: final, manager, self and calibrated grades; the calibration Δ is available too.
- By default the board shows the evaluations in calibration.
- Clicking a cell opens the editable calibration list (the action's list view): the
  calibrated grade, the mandatory note and, per line, its change log.
- The matrix is protected like the grades: a plain manager or an employee cannot read
  the grades through a grouped read (pivot), nor open the board's menu; a calibrator
  reads the whole campaign in calibration.
"""

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger
from odoo.tools.safe_eval import safe_eval

from .common import CampaignCase


@tagged("post_install", "-at_install")
class TestCalibrationPivot(CampaignCase):
    def _board_action(self, user=None):
        Action = self.env["ir.actions.act_window"]
        if user:
            Action = Action.with_user(user)
        return Action._for_xml_id("hr_appraisal_campaign.action_campaign_calibration_board")

    def _in_calibration(self):
        self.manager.parent_id = False  # the director is outside the reporting line
        appraisal = self.run_to_calibration(self_grade=3, manager_grade=2)
        colleague_app = self.campaign.appraisal_ids.filtered(lambda a: a.employee_id == self.colleague)
        self.set_self(colleague_app, [4] * self.n_criteria, user=self.colleague_user)
        colleague_app.with_user(self.colleague_user).action_campaign_submit_self()
        self.set_manager(colleague_app, [4] * self.n_criteria)
        colleague_app.with_user(self.manager_user).action_campaign_submit_manager()
        self.campaign.with_user(self.hr_user).action_start_calibration()
        return appraisal, colleague_app

    def test_board_opens_on_pivot_employee_by_criterion(self):
        action = self._board_action()
        view_types = [vtype for _vid, vtype in action["views"]]
        self.assertEqual(view_types[0], "pivot")
        self.assertIn("list", view_types)
        pivot_id = next(vid for vid, vtype in action["views"] if vtype == "pivot")
        list_id = next(vid for vid, vtype in action["views"] if vtype == "list")
        self.assertEqual(list_id, self.env.ref(
            "hr_appraisal_campaign.campaign_line_view_list_calibration").id)
        arch = etree.fromstring(self.env["ir.ui.view"].browse(pivot_id).arch)
        self.assertEqual(arch.xpath("//field[@type='row']/@name"), ["employee_id"])
        self.assertEqual(arch.xpath("//field[@type='col']/@name"), ["criterion_id"])
        self.assertEqual(arch.xpath("//field[@type='measure']/@name"), ["final_grade"])
        self.assertFalse(arch.get("sample"))
        context = safe_eval(action["context"]) if isinstance(action["context"], str) else action["context"]
        self.assertEqual(context.get("search_default_in_calibration"), 1)
        self.assertFalse(context.get("search_default_group_employee"),
                         "a pivot drill-down list must not come grouped")

    def test_grade_measures_average_not_sum(self):
        fields_ = self.env["hr.appraisal.campaign.line"]._fields
        for fname in ("final_grade", "manager_grade", "employee_grade", "calibrated_grade"):
            self.assertEqual(fields_[fname].aggregator, "avg", fname)
        self.assertTrue(fields_["final_vs_manager"].aggregator)

    def test_matrix_cells_are_grades_in_catalogue_order(self):
        appraisal, colleague_app = self._in_calibration()
        first = appraisal.campaign_line_ids[0].with_user(self.director_user)
        first.write({"calibrated_grade": 3, "calibration_note": "In line with the team"})
        Line = self.env["hr.appraisal.campaign.line"].with_user(self.director_user)
        domain = [("campaign_id", "=", self.campaign.id), ("campaign_step", "=", "calibration")]
        groups = Line.formatted_read_group(
            domain, ["employee_id", "criterion_id"], ["final_grade:avg", "manager_grade:avg"])
        cells = {(g["employee_id"][0], g["criterion_id"][0]): g for g in groups}
        self.assertEqual(len(cells), 2 * self.n_criteria)
        self.assertEqual(cells[(self.employee.id, first.criterion_id.id)]["final_grade:avg"], 3)
        self.assertEqual(cells[(self.employee.id, first.criterion_id.id)]["manager_grade:avg"], 2)
        self.assertEqual(cells[(self.colleague.id, first.criterion_id.id)]["final_grade:avg"], 4)
        # columns: the catalogue order
        columns = Line.formatted_read_group(domain, ["criterion_id"], ["final_grade:avg"])
        self.assertEqual([g["criterion_id"][0] for g in columns],
                         appraisal.campaign_line_ids.criterion_id.ids)
        self.assertEqual(appraisal.campaign_line_ids.criterion_id, self.criteria)
        # the row total of an employee is an average grade, not a sum
        rows = Line.formatted_read_group(domain, ["employee_id"], ["final_grade:avg"])
        row = next(g for g in rows if g["employee_id"][0] == self.colleague.id)
        self.assertEqual(row["final_grade:avg"], 4)

    def test_cell_list_change_log(self):
        appraisal, _colleague_app = self._in_calibration()
        line = appraisal.campaign_line_ids[0].with_user(self.director_user)
        line.write({"calibrated_grade": 3, "calibration_note": "In line with the team"})
        action = line.action_campaign_open_calibration_log()
        self.assertEqual(action["res_model"], "hr.appraisal.campaign.calibration.log")
        logs = self.env["hr.appraisal.campaign.calibration.log"].with_user(self.director_user).search(
            action["domain"])
        self.assertEqual((logs.old_grade, logs.new_grade, logs.user_id), (2, 3, self.director_user))
        list_arch = etree.fromstring(self.env.ref(
            "hr_appraisal_campaign.campaign_line_view_list_calibration").arch)
        self.assertTrue(list_arch.xpath("//button[@name='action_campaign_open_calibration_log']"))
        self.assertTrue(list_arch.xpath("//field[@name='calibrated_grade']"))
        self.assertTrue(list_arch.xpath("//field[@name='calibration_note']"))

    def test_pivot_protected_for_managers_and_employees(self):
        self._in_calibration()
        domain = [("campaign_id", "=", self.campaign.id)]
        for user in (self.manager_user, self.employee_user):
            Line = self.env["hr.appraisal.campaign.line"].with_user(user)
            for measure in ("final_grade:avg", "manager_grade:avg", "calibrated_grade:avg",
                            "final_vs_manager:sum"):
                with self.assertRaises(AccessError, msg=f"{user.login} {measure}"), \
                        mute_logger("odoo.models"):
                    Line.formatted_read_group(domain, ["employee_id", "criterion_id"], [measure])
        menu = self.env.ref("hr_appraisal_campaign.menu_campaign_calibration_board")
        for user in (self.manager_user, self.employee_user):
            visible = self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()
            self.assertNotIn(menu.id, visible, user.login)
        visible = self.env["ir.ui.menu"].with_user(self.director_user)._visible_menu_ids()
        self.assertIn(menu.id, visible)
