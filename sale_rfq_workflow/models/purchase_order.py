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

    def _find_candidate(self, product_id, product_qty, product_uom, location_id,
                        name, origin, company_id, values):
        """Merge an SO-driven buy procurement into the supply RFQ line the
        buyer already prepared for that exact SO line, keyed on
        ``supply_so_line_id``. Core would otherwise fail to match (its default
        candidate search compares the purchase description) and append a
        second line for the same demand.
        """
        sale_line_id = values.get('sale_line_id')
        if sale_line_id:
            adopted = self.filtered(
                lambda l: l.supply_so_line_id.id == sale_line_id
                and l.order_id.supply_sale_order_id
            )
            if adopted:
                return adopted[:1]
        return super()._find_candidate(
            product_id, product_qty, product_uom, location_id, name, origin,
            company_id, values)
