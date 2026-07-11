from odoo import fields, models


def _procurement_sale_line_id(values):
    """Sale-order line a procurement originates from, or False.

    Two shapes exist in the wild:
    - moveless buy values carry ``sale_line_id`` directly (bare
      ``mts_else_mto`` chaining, as deployed at fitcrew);
    - modules that chain the buy through real moves (e.g. Durpro's
      mrp_mts_else_mto forces ``move_dest_ids`` onto mts_else_mto
      procurements) drop ``sale_line_id`` from the buy values, but the
      destination delivery moves still know their sale line.
    Adoption must work in both (CI co-installs everything; found
    2026-07-10 when the whole-repo suite failed while the isolated
    module suite was green).
    """
    if values.get('sale_line_id'):
        return values['sale_line_id']
    moves = values.get('move_dest_ids')
    if moves:
        sale_lines = moves.mapped('sale_line_id')
        if sale_lines[:1]:
            return sale_lines[:1].id
    return False


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
        sale_line_id = _procurement_sale_line_id(values)
        if sale_line_id:
            supply_lines = self.filtered(
                lambda l: l.supply_so_line_id and l.sale_line_id.id == sale_line_id
            )
            if supply_lines:
                return supply_lines[0]
        return super()._find_candidate(product_id, product_qty, product_uom, location_id, name, origin, company_id, values)
