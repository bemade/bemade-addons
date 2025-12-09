from datetime import timedelta

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    expected_ship_date = fields.Date(
        string="Expected Ship Date",
        compute="_compute_expected_ship_date",
        inverse="_inverse_expected_ship_date",
        help="Expected date when this order line will be shipped.",
        store=True,
    )

    @api.depends("order_id.date_order", "customer_lead")
    def _compute_expected_ship_date(self):
        for line in self:
            if line.order_id.state in ("draft", "sent"):
                # For quotations, use today as the base date
                base_date = fields.Date.context_today(line)
            else:
                # For confirmed orders, use the actual order date
                base_date = (
                    line.order_id.date_order.date()
                    if line.order_id.date_order
                    else fields.Date.context_today(line)
                )

            if line.customer_lead:
                line.expected_ship_date = base_date + timedelta(days=line.customer_lead)
            else:
                line.expected_ship_date = base_date

    def _inverse_expected_ship_date(self):
        for line in self:
            if line.order_id.state in ("draft", "sent"):
                base_date = fields.Date.context_today(line)
            else:
                base_date = (
                    line.order_id.date_order.date()
                    if line.order_id.date_order
                    else fields.Date.context_today(line)
                )

            if line.expected_ship_date:
                delta = (line.expected_ship_date - base_date).days
                line.customer_lead = max(0, delta)
