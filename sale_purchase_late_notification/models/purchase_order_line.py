from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _auto_init(self):
        # Check if our column exists before letting Odoo create it
        self.env.cr.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'purchase_order_line'
            AND column_name = 'is_received'
        """
        )
        col_exists = bool(self.env.cr.fetchone())

        res = super()._auto_init()

        # Initialize via SQL to avoid ORM memory issues with large datasets
        if not col_exists:
            self.env.cr.execute(
                """
                UPDATE purchase_order_line
                SET is_received = (qty_received >= product_qty)
            """
            )
        return res

    is_late = fields.Boolean(
        string="Late",
        compute="_compute_is_late",
        search="_search_is_late",
    )

    is_received = fields.Boolean(
        string="Received",
        compute="_compute_is_received",
        store=True,
    )

    @api.depends("qty_received", "product_qty")
    def _compute_is_received(self):
        for line in self:
            line.is_received = line.qty_received >= line.product_qty

    def _search_is_late(self, operator, value):
        late_dom = [
            ("order_id.state", "=", "purchase"),
            ("date_planned", "<", fields.Datetime.now()),
            ("is_received", "=", False),
        ]
        not_late_dom = [
            ("order_id.state", "=", "purchase"),
            "|",
            ("date_planned", ">=", fields.Datetime.now()),
            ("is_received", "=", True),
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

    @api.depends("is_received", "order_id.state", "date_planned")
    def _compute_is_late(self):
        today = fields.Date.today()
        for line in self:
            line.is_late = (
                not line.is_received
                and line.order_id.state == "purchase"
                and line.date_planned
                and line.date_planned.date() < today
            )
