from datetime import timedelta

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = ["sale.order", "base.late.notification.mixin"]
    _name = "sale.order"

    _late_config_prefix = "sale"
    _late_activity_note = (
        "This sale order is late. Please review and take appropriate action."
    )

    is_late = fields.Boolean(
        string="Late",
        compute="_compute_is_late",
        search="_search_is_late",
    )

    def _search_is_late(self, operator, value):
        return [("order_line.is_late", operator, value)]

    @api.depends("state", "order_line.is_late")
    def _compute_is_late(self):
        for order in self:
            order.is_late = (
                any(order.order_line.mapped("is_late")) and order.state == "sale"
            )

    def _get_late_orders_domain(self):
        """Include threshold in domain for sale orders."""
        threshold_date = fields.Date.today() - timedelta(
            days=self._get_late_days_threshold()
        )
        return [
            ("is_late", "=", True),
            ("late_notification_date", "=", False),
            ("order_line.expected_ship_date", "<", threshold_date),
        ]
