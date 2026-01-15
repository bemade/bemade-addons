from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    sale_late_notification_delay = fields.Integer(string="Sale Late Notification Delay")
    purchase_late_notification_delay = fields.Integer(
        string="Purchase Late Notification Delay"
    )
