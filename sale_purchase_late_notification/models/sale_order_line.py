from datetime import timedelta

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    expected_ship_date = fields.Date(
        string="Expected Ship Date",
        compute="_compute_expected_ship_date",
        store=True,
        help="Expected date when this order line will be shipped.",
    )

    is_late = fields.Boolean(
        string="Late",
        compute="_compute_is_late",
        search="_search_is_late",
    )

    @api.depends("order_id.date_order", "customer_lead")
    def _compute_expected_ship_date(self):
        for line in self:
            if line.order_id.date_order:
                base_date = line.order_id.date_order.date()
            else:
                base_date = fields.Date.context_today(line)
            line.expected_ship_date = base_date + timedelta(
                days=line.customer_lead or 0
            )

    def _search_is_late(self, operator, value):
        # Use qty_to_deliver > 0 as proxy for "not fully delivered"
        # qty_to_deliver = product_uom_qty - qty_delivered (stored field on sale.order.line)
        late_dom = [
            ("order_id.state", "=", "sale"),
            ("expected_ship_date", "<", fields.Date.today()),
            ("qty_to_deliver", ">", 0),
        ]
        not_late_dom = [
            ("order_id.state", "=", "sale"),
            "|",
            ("expected_ship_date", ">=", fields.Date.today()),
            ("qty_to_deliver", "<=", 0),
        ]

        if operator == "=":
            return late_dom if value else not_late_dom
        if operator == "!=":
            return not_late_dom if value else late_dom
        if operator == "in":
            if False in value and True in value:
                return [("order_id.state", "=", "sale")]
            elif True in value:
                return late_dom
            elif False in value:
                return not_late_dom
        if operator == "not in":
            if False in value and True in value:
                return []
            elif True in value:
                return not_late_dom
            elif False in value:
                return late_dom
        return []

    @api.depends("qty_to_deliver", "order_id.state", "expected_ship_date")
    def _compute_is_late(self):
        today = fields.Date.today()
        for line in self:
            line.is_late = (
                line.qty_to_deliver > 0
                and line.order_id.state == "sale"
                and line.expected_ship_date
                and line.expected_ship_date < today
            )
