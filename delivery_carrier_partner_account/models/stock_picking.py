from odoo import models, fields, api


class Picking(models.Model):
    _inherit = ["stock.picking", "carrier.account.mixin"]
    _name = "stock.picking"

    recipient_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_sender_recipient",
    )
    sender_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_sender_recipient",
    )

    def _compute_sender_recipient(self):
        for picking in self:
            dest_usage = picking.location_dest_id.usage
            src_usage = picking.location_id.usage
            match (src_usage, dest_usage):
                case ("internal", "customer") | ("internal", "supplier"):
                    picking.recipient_id = picking.partner_id
                    picking.sender_id = picking.picking_type_id.warehouse_id.partner_id or picking.company_id.partner_id
                case ("customer", "internal") | ("supplier", "internal"):
                    picking.recipient_id = picking.picking_type_id.warehouse_id.partner_id or picking.company_id.partner_id
                    picking.sender_id = picking.partner_id
                case _:
                    picking.recipient_id = picking.location_dest_id.warehouse_id.partner_id or picking.partner_id
                    picking.sender_id = picking.location_id.warehouse_id.partner_id or picking.partner_id

    def _add_delivery_cost_to_so(self):
        self.ensure_one()
        if not self.delivery_billing_mode or self.delivery_billing_mode != "ppc":
            super()._add_delivery_cost_to_so()
        else:
            sale_order = self.sale_id
            delivery_lines = self._get_matching_delivery_lines()
            if not delivery_lines:
                delivery_lines = sale_order.with_context(
                    delivery_billing_mode="ppc", carrier_account=self.carrier_account_id
                )._create_delivery_line(self.carrier_id, self.carrier_price)
            vals = self._prepare_sale_delivery_line_vals()
            delivery_lines[0].write(vals)
