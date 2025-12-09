from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_late = fields.Boolean(
        string="Late",
        compute="_compute_is_late",
        search="_search_is_late",
    )

    is_delivered = fields.Boolean(
        string="Delivered",
        compute="_compute_is_delivered",
        store=True,
    )

    @api.depends("qty_delivered", "product_uom_qty")
    def _compute_is_delivered(self):
        for line in self:
            line.is_delivered = line.qty_delivered >= line.product_uom_qty

    def _search_is_late(self, operator, value):
        late_dom = [
            ("order_id.state", "=", "sale"),
            ("expected_ship_date", "<", fields.Date.today()),
            ("is_delivered", "=", False),
        ]
        not_late_dom = [
            ("order_id.state", "=", "sale"),
            "|",
            ("expected_ship_date", ">=", fields.Date.today()),
            ("is_delivered", "=", True),
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

    @api.depends("is_delivered", "order_id.state", "expected_ship_date")
    def _compute_is_late(self):
        today = fields.Date.today()
        for line in self:
            line.is_late = (
                not line.is_delivered
                and line.order_id.state == "sale"
                and line.expected_ship_date
                and line.expected_ship_date < today
            )
