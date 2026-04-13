from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    sale_late_notification_delay = fields.Integer(
        string="Sale Late Notification Delay",
        help="Number of days to wait before creating follow-up tasks for late sales"
        " orders for this client. This setting overrides the global setting.",
    )
    purchase_late_notification_delay = fields.Integer(
        string="Purchase Late Notification Delay",
        help="Number of days to wait before creating follow-up tasks for late purchase"
        " orders for this client. This setting overrides the global setting.",
    )
