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

    def write(self, vals):
        res = super().write(vals)
        for partner in self.partner_id.filtered(
            lambda partner: not partner.default_carrier_account_id
        ):
            partner.default_carrier_account_id = partner.carrier_account_ids[0]
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            if not rec.partner_id.default_carrier_account_id:
                rec.partner_id.default_carrier_account_id = rec
        return res
