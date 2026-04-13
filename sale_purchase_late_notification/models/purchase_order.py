from datetime import timedelta

from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "base.late.notification.mixin"]

    _late_config_prefix = "purchase"
    _late_activity_note = (
        "This purchase order is late. Please review and take appropriate action."
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
                any(order.order_line.mapped("is_late")) and order.state == "purchase"
            )

    @api.depends("late_days_threshold")
    def _compute_is_past_threshold(self):
        """Check if sale order is past its late days threshold."""
        for order in self:
            threshold_date = fields.Date.today() - timedelta(
                days=order.late_days_threshold
            )
            order.is_past_threshold = any(
                line.date_planned and line.date_planned.date() < threshold_date
                for line in order.order_line  # pyright: ignore[reportAttributeAccessIssue]
            )
