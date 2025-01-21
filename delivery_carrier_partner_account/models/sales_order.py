from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


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

    def _create_delivery_line(self, carrier, price_unit):
        line = super()._create_delivery_line(carrier, price_unit)
        name = line.name
        delivery_billing_mode = self.delivery_billing_mode
        carrier_account = self.carrier_account_id
        if delivery_billing_mode:
            mode_display = delivery_billing_mode.upper()
            name = name + f" [{mode_display}]"
        if delivery_billing_mode in ["collect", "third party"] and carrier_account:
            name = name + f" #{carrier_account.account_number}"
        line.name = name
        return line

    def _on_carrier_fields_changed(self):
        """Propagate carrier field changes to pickings."""
        super()._on_carrier_fields_changed()
        _logger.debug("In sale_order._on_carrier_fields_changed")
        for rec in self:
            for picking in rec.picking_ids.filtered(
                lambda pick: pick.state not in ["done", "cancel"]
            ):
                _logger.debug("Writing to picking")
                picking.write(
                    {
                        "carrier_id": rec.carrier_id and rec.carrier_id.id,
                        "delivery_billing_mode": rec.delivery_billing_mode,
                        "carrier_account_id": (
                            rec.carrier_account_id and rec.carrier_account_id.id
                        ),
                    }
                )
