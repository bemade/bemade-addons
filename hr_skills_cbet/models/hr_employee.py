from odoo import api, models


class HrEmployee(models.Model):
    """UC-STD-06 — keep job-derived qualifications in step with the employee's
    position and active flag."""

    _inherit = "hr.employee"

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        self.env["cbet.qualification"]._sync_job_requirements(employees)
        return employees

    def write(self, vals):
        res = super().write(vals)
        if {"job_id", "active", "version_id"} & set(vals):
            self.env["cbet.qualification"]._sync_job_requirements(self)
        return res

    def _cron_update_current_version_id(self):
        # A dated contract version becoming current can change the position
        # without any write on the employee.
        res = super()._cron_update_current_version_id()
        self.env["cbet.qualification"]._sync_job_requirements(
            self.with_context(active_test=False).search([]))
        return res


class HrVersion(models.Model):
    _inherit = "hr.version"

    def write(self, vals):
        res = super().write(vals)
        if "job_id" in vals:
            self.env["cbet.qualification"]._sync_job_requirements(self.employee_id)
        return res
