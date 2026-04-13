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

    @api.depends("late_days_threshold")
    def _compute_is_past_threshold(self):
        """Check if sale order is past its late days threshold."""
        for order in self:
            threshold_date = fields.Date.today() - timedelta(
                days=order.late_days_threshold
            )
            order.is_past_threshold = any(
                line.expected_ship_date and line.expected_ship_date < threshold_date
                for line in order.order_line  # pyright: ignore[reportAttributeAccessIssue]
            )