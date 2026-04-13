# -*- coding: utf-8 -*-
from odoo import fields, models


class LostMessageSubcategory(models.Model):
    """Subcategory for classifying lost messages."""
    _name = 'lost.message.subcategory'
    _description = 'Lost Message Subcategory'
    _order = 'sequence, name'

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True)
    description = fields.Text(string="Description", translate=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    color = fields.Integer(string="Color")
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)', 'Code must be unique per company!'),
    ]
