# -*- coding: utf-8 -*-
from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"

    homeschool_student_ids = fields.One2many(
        "homeschool.student", "company_id", string="Home-schooled students",
        help="The students of this family. Used by the portal record rules: a portal user reaches "
        "the institutional traces and material of the companies whose students he is attached to.",
    )
