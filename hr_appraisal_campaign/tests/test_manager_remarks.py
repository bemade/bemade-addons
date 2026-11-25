"""Manager remarks after « Submit for Calibration ».

Acceptance criteria:
- The manager (and HR) can still edit the remarks at the calibration and meeting steps,
  before and after « Meeting held », until the employee acknowledges the evaluation;
  after the acknowledgement they are frozen for everyone.
- The employee, a calibrating director and a colleague never edit the remarks.
- The manager's GRADES stay locked from « Submit for Calibration » on (only the
  calibrated grade moves, in calibration).
- Every remark change after the submission is logged (who, step, before → after) in a
  log HR reads; nothing of it goes to the chatter (the employee follows the evaluation).
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import CampaignCase

EDIT_ERRORS = (AccessError, UserError)


@tagged("post_install", "-at_install")
class TestManagerRemarks(CampaignCase):
    def _stages(self):
        """Walk one evaluation through every stage, yielding (stage, appraisal)."""
        appraisal = self.launch()
        yield "self_eval", appraisal
        self.set_self(appraisal, [3] * self.n_criteria)
        appraisal.with_user(self.employee_user).action_campaign_submit_self()
        yield "manager_eval", appraisal
        self.set_manager(appraisal, [3] * self.n_criteria)
        appraisal.with_user(self.manager_user).action_campaign_submit_manager()
        self.campaign.with_user(self.hr_user).action_start_calibration()
        yield "calibration", appraisal
        self.campaign.with_user(self.hr_user).action_close_calibration()
        yield "meeting", appraisal
        appraisal.with_user(self.manager_user).action_campaign_share()
        yield "meeting_held", appraisal
        appraisal.with_user(self.employee_user).action_campaign_acknowledge()
        yield "employee_acknowledged", appraisal
        appraisal.with_user(self.manager_user).action_campaign_validate()
        yield "acknowledged", appraisal
        appraisal.with_user(self.hr_user).action_campaign_close()
        yield "closed", appraisal

    def _try_write(self, line, user, vals):
        try:
            with self.env.cr.savepoint(), mute_logger("odoo.models"):
                line.with_user(user).write(vals)
        except EDIT_ERRORS:
            return False
        return True

    def test_remark_editing_role_by_step(self):
        editable_steps = {"manager_eval", "calibration", "meeting", "meeting_held"}
        roles = {
            "employee": self.employee_user,
            "manager": self.manager_user,
            "hr": self.hr_user,
            "director": self.director_user,
        }
        for stage, appraisal in self._stages():
            line = appraisal.campaign_line_ids[0]
            for role, user in roles.items():
                expected = stage in editable_steps and role in ("manager", "hr")
                line.invalidate_recordset()
                with self.subTest(stage=stage, role=role):
                    allowed = self._try_write(
                        line, user, {"manager_remarks_ui": f"{stage} by {role}"})
                    self.assertEqual(allowed, expected)
                    if stage != "self_eval":
                        flag = line.with_user(user).can_edit_remarks
                        self.assertEqual(flag, expected)

    def test_manager_grades_locked_after_submit(self):
        for stage, appraisal in self._stages():
            if stage in ("self_eval", "manager_eval"):
                continue
            line = appraisal.campaign_line_ids[0]
            for user in (self.manager_user, self.hr_user):
                with self.subTest(stage=stage, user=user.login):
                    self.assertFalse(self._try_write(line, user, {"manager_grade_ui": 1}))
            with self.subTest(stage=stage, user="hr-direct"):
                self.assertFalse(self._try_write(line, self.hr_user, {"manager_grade": 1}))
            self.assertEqual(line.sudo().manager_grade, 3)

    def test_hr_direct_remark_write_follows_the_rule(self):
        stages = self._stages()
        for stage, appraisal in stages:
            if stage == "employee_acknowledged":
                break
        line = appraisal.campaign_line_ids[0]
        self.assertFalse(self._try_write(line, self.hr_user, {"manager_remarks": "late change"}))

    def test_remark_changes_logged_not_in_chatter(self):
        Log = self.env["hr.appraisal.campaign.remark.log"]
        for stage, appraisal in self._stages():
            line = appraisal.campaign_line_ids[0]
            if stage == "manager_eval":
                line.with_user(self.manager_user).write({"manager_remarks_ui": "FIRST-DRAFT"})
                self.assertFalse(Log.search([("line_id", "=", line.id)]),
                                 "drafting before the submission is not logged")
            elif stage == "calibration":
                line.with_user(self.manager_user).write({"manager_remarks_ui": "REFINED-AFTER-SUBMIT"})
            elif stage == "meeting_held":
                line.with_user(self.hr_user).write({"manager_remarks_ui": "AMENDED-AT-MEETING"})
                break
        logs = Log.search([("line_id", "=", line.id)], order="id")
        self.assertEqual(len(logs), 2)
        self.assertEqual(
            [(log.user_id, log.step, log.old_remarks, log.new_remarks) for log in logs],
            [(self.manager_user, "calibration", "FIRST-DRAFT", "REFINED-AFTER-SUBMIT"),
             (self.hr_user, "meeting", "REFINED-AFTER-SUBMIT", "AMENDED-AT-MEETING")])
        # HR reads the log; the employee and the manager do not
        self.assertEqual(len(Log.with_user(self.hr_user).search([("line_id", "=", line.id)])), 2)
        for user in (self.employee_user, self.manager_user):
            with self.assertRaises(AccessError), mute_logger("odoo.models"):
                Log.with_user(user).search([("line_id", "=", line.id)])
        bodies = " ".join(str(m.body) for m in appraisal.message_ids)
        for text in ("FIRST-DRAFT", "REFINED-AFTER-SUBMIT", "AMENDED-AT-MEETING"):
            self.assertNotIn(text, bodies)
