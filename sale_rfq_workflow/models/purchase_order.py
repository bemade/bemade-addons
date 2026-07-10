from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    supply_sale_order_id = fields.Many2one(
        'sale.order',
        string='Source Sales Order',
        ondelete='set null',
        copy=False,
        index=True,
    )

    def action_view_supply_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.supply_sale_order_id.id,
            'target': 'current',
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    supply_so_line_id = fields.Many2one(
        'sale.order.line',
        string='Source SO Line',
        ondelete='set null',
        copy=False,
        index=True,
    )

    def _find_candidate(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values):
        # A supply RFQ line generated from this exact SO line is always the
        # merge candidate — the standard filters (propagate_cancel, uom, name
        # variants) must not push the procurement onto a duplicate line.
        if not values.get('move_dest_ids') and values.get('sale_line_id'):
            supply_lines = self.filtered(
                lambda l: l.supply_so_line_id and l.sale_line_id.id == values['sale_line_id']
            )
            if supply_lines:
                return supply_lines[0]
        return super()._find_candidate(product_id, product_qty, product_uom, location_id, name, origin, company_id, values)
