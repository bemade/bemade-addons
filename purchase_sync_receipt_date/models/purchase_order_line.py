# Copyright 2025 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def write(self, vals):
        """Override to sync scheduled date on receipts when date_planned changes."""
        res = super().write(vals)

        # Only sync if the setting is enabled and date_planned was changed
        if self.env.company.purchase_sync_receipt_date and not self.display_type:
            self.move_ids.filtered(lambda m: m.state not in ("done", "cancel")).write(
                {"date": vals["date_planned"]}
            )
        return res
