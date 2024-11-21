from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DeliveryCarrierAccount(models.Model):
    _name = "delivery.carrier.account"
    _description = "Delivery Carrier Account"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    delivery_carrier_id = fields.Many2one(
        comodel_name="delivery.carrier",
        string="Delivery Carriers",
        required=True,
        ondelete="restrict",
    )

    account_number = fields.Char(
        required=True,
        tracking=1,
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        required=True,
        ondelete="cascade",
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        related="delivery_carrier_id.company_id",
    )

    active = fields.Boolean(
        default=True,
    )

    @api.depends("account_number")
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.account_number

    @api.constrains("partner_id", "delivery_carrier_id")
    def _constrain_partner_carrier_same_company(self):
        for rec in self:
            if rec.partner_id.company_id != rec.delivery_carrier_id.company_id:
                raise UserError(_("Partner and Carrier must be in the same company."))
