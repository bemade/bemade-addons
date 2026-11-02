from odoo import fields, models


class HrJob(models.Model):
    """UC-STD-06 — a job position lists the CBET standards it requires."""

    _inherit = "hr.job"

    cbet_standard_ids = fields.Many2many(
        "cbet.standard", "cbet_standard_hr_job_rel", "job_id", "standard_id",
        string="Required CBET standards",
        help="Every employee in this position qualifies against these standards: "
             "their gaps show in the training matrix.",
    )

    def write(self, vals):
        res = super().write(vals)
        if "cbet_standard_ids" in vals:
            employees = self.env["hr.employee"].sudo().search([("job_id", "in", self.ids)])
            self.env["cbet.qualification"]._sync_job_requirements(employees)
        return res
