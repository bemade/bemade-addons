from odoo import models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_supply_rfq_line(self, values):
        """Return the supply RFQ line generated from the procurement's source
        SO line, if one exists on a living order.

        Only moveless, SO-originated procurements are considered — move-chained
        (MTO/dropship) procurements keep the standard behaviour.
        """
        sale_line_id = values.get('sale_line_id')
        if not sale_line_id or values.get('move_dest_ids'):
            return self.env['purchase.order.line']
        return self.env['purchase.order.line'].sudo().search([
            ('sale_line_id', '=', sale_line_id),
            ('supply_so_line_id', '!=', False),
            ('order_id.supply_sale_order_id', '!=', False),
            ('order_id.state', 'in', ('draft', 'sent', 'purchase')),
        ], order='id desc', limit=1)

    def _get_matching_supplier(self, product_id, product_qty, product_uom, company_id, values):
        # The vendor chosen at RFQ generation is authoritative: without this,
        # _select_seller could route the procurement to another vendor and the
        # linked RFQ would never be matched.
        supply_line = self._get_supply_rfq_line(values)
        if supply_line:
            vendor = supply_line.order_id.partner_id
            supplier = product_id.with_company(company_id.id)._select_seller(
                partner_id=vendor,
                quantity=product_qty,
                uom_id=product_uom,
                params={'force_uom': values.get('force_uom')},
            )
            supplier = supplier or product_id._prepare_sellers(False).filtered(
                lambda s: s.partner_id == vendor
                and (not s.company_id or s.company_id == company_id)
            )[:1]
            if supplier:
                return supplier
        return super()._get_matching_supplier(product_id, product_qty, product_uom, company_id, values)

    def _make_po_get_domain(self, company_id, values, partner):
        # Adopt the linked supply RFQ even after it was sent to the vendor —
        # the core domain only matches state='draft', which is precisely what
        # regenerates a fresh RFQ once the linked one has been quoted.
        supply_line = self._get_supply_rfq_line(values)
        if supply_line and supply_line.order_id.partner_id == partner:
            return (('id', '=', supply_line.order_id.id),)
        return super()._make_po_get_domain(company_id, values, partner)

    def _update_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, line):
        res = super()._update_purchase_order_line(product_id, product_qty, product_uom, company_id, values, line)
        if line.supply_so_line_id and values.get('sale_line_id') == line.supply_so_line_id.id:
            # The RFQ line already covers this SO line's demand: track the SO
            # quantity instead of accumulating procurement quantities (initial
            # confirmation would double it), and keep any larger quantity a
            # buyer set manually.
            so_line = line.supply_so_line_id
            demand_qty = so_line.product_uom_id._compute_quantity(
                so_line.product_uom_qty, line.product_uom_id, rounding_method='HALF-UP')
            res['product_qty'] = max(line.product_qty, demand_qty)
            res.pop('product_uom_id', None)
            if not line.currency_id.is_zero(line.price_unit):
                # The quoted price on the RFQ is authoritative over the
                # supplier-info price the core merge would write.
                res.pop('price_unit', None)
        return res
