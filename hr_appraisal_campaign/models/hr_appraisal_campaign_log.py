from odoo import fields, models

from .hr_appraisal_campaign import STEPS


class HrAppraisalCampaignCalibrationLog(models.Model):
    _name = "hr.appraisal.campaign.calibration.log"
    _description = "Evaluation Calibration Change"
    _order = "create_date desc, id desc"

    line_id = fields.Many2one(
        "hr.appraisal.campaign.line", required=True, ondelete="cascade", index=True)
    appraisal_id = fields.Many2one(related="line_id.appraisal_id", store=True)
    employee_id = fields.Many2one(related="line_id.appraisal_id.employee_id", store=True)
    company_id = fields.Many2one(related="line_id.appraisal_id.company_id", store=True)
    criterion_name = fields.Char(related="line_id.name")
    user_id = fields.Many2one("res.users", "Changed by", required=True, default=lambda s: s.env.user)
    old_grade = fields.Integer("From")
    new_grade = fields.Integer("To")
    note = fields.Text()


class HrAppraisalCampaignRemarkLog(models.Model):
    """Changes to the manager's remarks after « Submit for Calibration ».

    Kept out of the chatter on purpose: the employee follows the evaluation and must not
    read the remarks before the meeting.
    """

    _name = "hr.appraisal.campaign.remark.log"
    _description = "Evaluation Remark Change"
    _order = "create_date desc, id desc"

    line_id = fields.Many2one(
        "hr.appraisal.campaign.line", required=True, ondelete="cascade", index=True)
    appraisal_id = fields.Many2one(related="line_id.appraisal_id", store=True)
    employee_id = fields.Many2one(related="line_id.appraisal_id.employee_id", store=True)
    company_id = fields.Many2one(related="line_id.appraisal_id.company_id", store=True)
    criterion_name = fields.Char(related="line_id.name")
    user_id = fields.Many2one("res.users", "Changed by", required=True, default=lambda s: s.env.user)
    step = fields.Selection(STEPS, "Evaluation Step")
    old_remarks = fields.Text("Before")
    new_remarks = fields.Text("After")
