from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    delivery_carrier_id = fields.Many2one(
        comodel_name="delivery.carrier",
        string="Delivery Carrier",
        compute="_compute_delivery_carrier_id",
        inverse="_inverse_delivery_carrier_id",
        store=True,
    )

    @api.depends("partner_id")
    def _compute_delivery_carrier_id(self):
        for rec in self:
            rec.delivery_carrier_id = rec.partner_id.delivery_carrier_id

    def _inverse_delivery_carrier_id(self):
        pass

    def _prepare_picking(self):
        res = super()._prepare_picking()
        res.update(carrier_id=self.delivery_carrier_id.id)
        return res
