# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    purchase_decrease_ignore_cost = fields.Boolean(
        string="Reduce Receipts Regardless of Cost",
        help="When the quantity of a confirmed purchase order line is lowered, "
        "reduce its open receipt even if the cost converted to the company "
        "currency has changed since the order was confirmed (for instance "
        "after a new exchange rate was loaded), instead of creating a return.",
    )
