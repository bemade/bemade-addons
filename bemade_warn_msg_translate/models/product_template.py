# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    sale_line_warn_msg = fields.Text(translate=True)
    purchase_line_warn_msg = fields.Text(translate=True)
