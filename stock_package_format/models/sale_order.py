# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        # Plan on the quotation state, before the order reserves stock.
        plan = self.filtered(lambda o: o.state in ("draft", "sent")).order_line._package_format_buy_plan()
        res = super().action_confirm()
        if plan:
            self.order_line._package_format_buy(plan)
        return res
