# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    sale_warn_msg = fields.Text(translate=True)
    purchase_warn_msg = fields.Text(translate=True)
    picking_warn_msg = fields.Text(translate=True)
