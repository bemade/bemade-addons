from odoo import fields, models, api


class DeliveryCarrierAccount(models.Model):
    _inherit = "delivery.carrier.account"

    supplier_ids = fields.One2many(
        comodel_name="res.partner",
        inverse_name="purchase_delivery_carrier_account_id",
        string="Suppliers",
    )
