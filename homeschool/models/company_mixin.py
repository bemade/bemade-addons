# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CompanyMixin(models.AbstractModel):
    """A family-owned record: it belongs to one company (the family).

    Managers only see the companies they are attached to (record rules); relational fields
    flagged ``check_company=True`` must point to records of the same family. On create, a
    record made for a student takes the student's company; otherwise the current company.
    """
    _name = "homeschool.company.mixin"
    _description = "Family-owned record"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company", string="Company", required=True, index=True, default=lambda self: self.env.company,
        help="The family this record belongs to.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if "student_id" in self._fields:
            Student = self.env["homeschool.student"]
            for vals in vals_list:
                if vals.get("student_id") and not vals.get("company_id"):
                    vals["company_id"] = Student.browse(vals["student_id"]).company_id.id
        return super().create(vals_list)
