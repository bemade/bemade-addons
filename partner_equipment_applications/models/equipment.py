from odoo import models, fields


class Equipment(models.Model):
    _inherit = "fsm.equipment"

    application_id = fields.Many2one(
        comodel_name="partner.application",
        tracking=1,
        domain="[('partner_id', '=', partner_id)]",
        ondelete="restrict",
    )
    application_type_id = fields.Many2one(
        comodel_name="partner.application.type",
        related="application_id.application_type_id",
        readonly=True,
    )
