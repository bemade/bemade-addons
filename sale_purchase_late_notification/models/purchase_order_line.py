from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    is_late = fields.Boolean(
        string="Late",
        compute="_compute_is_late",
        search="_search_is_late",
    )

    def _search_is_late(self, operator, value):
        # Find lines where qty_received < product_qty using SQL subquery
        # since Odoo domains don't support field-to-field comparison
        self.env.cr.execute(
            """
            SELECT id FROM purchase_order_line
            WHERE qty_received < product_qty
        """
        )
        not_fully_received_ids = [r[0] for r in self.env.cr.fetchall()]

        late_dom = [
            ("order_id.state", "=", "purchase"),
            ("date_planned", "<", fields.Datetime.now()),
            ("id", "in", not_fully_received_ids),
        ]
        not_late_dom = [
            ("order_id.state", "=", "purchase"),
            "|",
            ("date_planned", ">=", fields.Datetime.now()),
            ("id", "not in", not_fully_received_ids),
        ]

        if operator == "=":
            return late_dom if value else not_late_dom
        if operator == "!=":
            return not_late_dom if value else late_dom
        if operator == "in":
            if False in value and True in value:
                return [("order_id.state", "=", "purchase")]
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

    @api.depends("qty_received", "product_qty", "order_id.state", "date_planned")
    def _compute_is_late(self):
        today = fields.Date.today()
        for line in self:
            line.is_late = (
                line.qty_received < line.product_qty
                and line.order_id.state == "purchase"
                and line.date_planned
                and line.date_planned.date() < today
            )
