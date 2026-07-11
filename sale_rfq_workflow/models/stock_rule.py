from odoo import models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _make_po_get_domain(self, company_id, values, partner):
        """Route a Sales-Order-driven buy procurement into the supply RFQ the
        buyer already prepared for that SO, instead of letting core spin up a
        brand-new duplicate PO.

        The wizard-generated RFQ carries ``supply_sale_order_id`` and each of
        its lines carries ``supply_so_line_id``. When the procurement we are
        about to run belongs to a sale order line that one of those RFQs
        already covers, we return a domain matching *that* RFQ by id — even
        when it is in the quoted (``sent``) state, which core's stock/currency
        domain would otherwise exclude — so ``_run_buy`` adopts it. This also
        honours the buyer's manual vendor grouping over ``_select_seller``.
        """
        rfq = self._get_adoptable_supply_rfq(company_id, values)
        if rfq:
            return (
                ('id', '=', rfq.id),
                ('company_id', '=', company_id.id),
            )
        return super()._make_po_get_domain(company_id, values, partner)

    def _get_adoptable_supply_rfq(self, company_id, values):
        """Return the not-yet-confirmed supply RFQ that already covers the
        procurement's sale order line, or an empty recordset."""
        sale_line_id = values.get('sale_line_id')
        if not sale_line_id:
            return self.env['purchase.order']
        sol = self.env['sale.order.line'].browse(sale_line_id).exists()
        if not sol:
            return self.env['purchase.order']
        rfqs = sol.order_id.supply_rfq_ids.filtered(
            lambda p: p.state in ('draft', 'sent', 'purchase')
            and p.company_id.id == company_id.id
            and sale_line_id in p.order_line.filtered('supply_so_line_id')
            .supply_so_line_id.ids
        )
        # Prefer a still-editable RFQ (draft/sent) over an already-confirmed
        # one so we adopt where we can still adjust qty/price cleanly.
        return rfqs.sorted(lambda p: p.state == 'purchase')[:1]

    def _update_purchase_order_line(self, product_id, product_qty, product_uom,
                                    company_id, values, line):
        """When merging a procurement into an *adopted* supply RFQ line, do not
        double the quantity the buyer already set, and never clobber the price
        the quote analyzer applied.

        - First adoption (the line is not yet chained to any demand move): just
          attach the demand move(s); the buyer-chosen qty and analyzed price
          stand.
        - Later delta procurement (SO qty raised after the line was already
          chained): let core add the extra qty, but keep the analyzed price.
        """
        if self._is_adopted_supply_line(values, line):
            if not line.move_dest_ids:
                dest_moves = values.get('move_dest_ids') \
                    or self.env['stock.move']
                # An already-confirmed RFQ line has its own incoming receipt
                # move. Simply attaching move_dest_ids to the line does not
                # re-chain that existing move, so the SO delivery would be left
                # orphaned. Splice the receipt into the demand move chain so
                # the incoming stock genuinely feeds the delivery.
                self._thread_supply_receipt_into_demand(line, dest_moves)
                return {
                    'move_dest_ids': [(4, m.id) for m in dest_moves],
                }
            vals = super()._update_purchase_order_line(
                product_id, product_qty, product_uom, company_id, values, line)
            vals.pop('price_unit', None)
            return vals
        return super()._update_purchase_order_line(
            product_id, product_qty, product_uom, company_id, values, line)

    def _thread_supply_receipt_into_demand(self, line, dest_moves):
        """Chain an already-confirmed supply RFQ line's incoming receipt move
        onto the SO delivery (``dest_moves``) so the demand is satisfied by the
        stock that is already on order — no orphaned delivery, no new RFQ."""
        if not dest_moves:
            return
        incoming = line.move_ids.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.location_id.usage == 'supplier'
        )
        if not incoming:
            return
        # sudo() mirrors core's _run_buy merge path — the SO may be confirmed
        # by a sales/portal user without stock write access.
        incoming.sudo().write({'move_dest_ids': [(4, m.id) for m in dest_moves]})
        dest_moves.sudo().write({
            'procure_method': 'make_to_order',
            'move_orig_ids': [(4, m.id) for m in incoming],
        })

    def _is_adopted_supply_line(self, values, line):
        sale_line_id = values.get('sale_line_id')
        return bool(
            sale_line_id
            and line.supply_so_line_id.id == sale_line_id
            and line.order_id.supply_sale_order_id
        )
