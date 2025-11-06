from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = ["purchase.order", "carrier.account.mixin"]
    _name = "purchase.order"

    _default_carrier_field = "purchase_delivery_carrier_id"
    _default_account_field = "purchase_delivery_carrier_account_id"

    recipient_id = fields.Many2one(
        comodel_name="res.partner",
        string="Recipient",
        related="picking_type_id.warehouse_id.partner_id",
    )

    sender_id = fields.Many2one(
        comodel_name="res.partner",
        string="Sender",
        related="partner_id",
    )

    def _prepare_picking(self):
        res = super()._prepare_picking()
        res.update(
            carrier_id=self.carrier_id.id,
            delivery_billing_mode=self.delivery_billing_mode,
            carrier_account_id=self.carrier_account_id.id,
        )
        return res

    @api.model_create_multi
    def create(self, vals_list):
        def _set_default_carrier_and_account_id(vals):
            vendor = self.env["res.partner"].browse(vals.get("partner_id"))
            vals["carrier_id"] = (
                vals.get("carrier_id") or vendor.purchase_delivery_carrier_id.id
            )
            vals["carrier_account_id"] = (
                vals.get("carrier_account_id")
                or vendor.purchase_delivery_carrier_account_id.id
            )

        for vals in vals_list:
            _set_default_carrier_and_account_id(vals)
        return super().create(vals_list)

    def _on_carrier_fields_changed(self):
        """Propagate carrier field changes to pickings."""
        super()._on_carrier_fields_changed()
        for rec in self:
            for picking in rec.picking_ids.filtered(
                lambda pick: pick.state not in ["done", "cancel"]
            ):
                picking.with_context(no_carrier_update=True).write(
                    {
                        "carrier_id": rec.carrier_id.id if rec.carrier_id else False,
                        "carrier_account_id": (
                            rec.carrier_account_id.id
                            if rec.carrier_account_id
                            else False
                        ),
                        "delivery_billing_mode": rec.delivery_billing_mode,
                    }
                )
