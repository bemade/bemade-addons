from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "base.late.notification.mixin"]

    _late_config_prefix = "purchase"
    _late_date_field = "order_line.date_planned"
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
