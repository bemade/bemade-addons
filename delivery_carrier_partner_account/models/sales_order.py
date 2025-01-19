from odoo import models, fields, api, _


class SalesOrder(models.Model):
    _inherit = ["sale.order", "carrier.account.mixin"]
    _name = "sale.order"

    recipient_id = fields.Many2one(
        comodel_name="res.partner",
        related="partner_id",
    )
    sender_id = fields.Many2one(
        comodel_name="res.partner",
        related="warehouse_id.partner_id",
    )

    @api.model
    def write(self, vals):
        res = super().write(vals)
        if (
            "carrier_account_id" in vals
            or "carrier_id" in vals
            or "delivery_billing_mode" in vals
        ):
            for rec in self.filtered(
                lambda order: order.state not in ["draft", "sent"]
            ):
                for picking in rec.picking_ids.filtered(
                    lambda pick: pick.state not in ["done", "cancel"]
                ):
                    picking.write(
                        {
                            "carrier_id": rec.carrier_id,
                            "carrier_account_id": rec.carrier_account_id,
                            "delivery_billing_mode": rec.delivery_billing_mode,
                        }
                    )
        return res

    def _create_delivery_line(self, carrier, price_unit):
        line = super()._create_delivery_line(carrier, price_unit)
        name = line.name
        delivery_billing_mode = self.delivery_billing_mode or self.env.context.get(
            "delivery_billing_mode", False
        )
        carrier_account = self.carrier_account_id or self.env.context.get(
            "carrier_account", False
        )
        if delivery_billing_mode:
            name = name + f" [{delivery_billing_mode.upper()}]"
        if delivery_billing_mode in ["collect", "third party"] and carrier_account:
            name = name + f" #{carrier_account.account_number}"
        line.name = name
        return line
