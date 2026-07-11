from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_analyse_quote(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.quote.analysis.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_order_id': self.id},
        }

    def _post_apply_landed_costs(self, fee_lines):
        """Hook called after the quote analyzer created/updated landed-cost fee
        lines on this purchase order.

        No-op by default: this module only puts the fee lines on the RFQ so its
        total matches the vendor quote. Downstream modules may override this to
        react to ``fee_lines`` (e.g. mirror them onto a linked Sales Order).
        """
        return


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    is_landed_cost_fee = fields.Boolean(
        string='Landed-Cost Fee Line',
        default=False,
        copy=False,
        help="Set on RFQ lines the quote analyzer created from a vendor "
             "landed-cost charge (freight, handling, duty). Such lines carry a "
             "quoted fee rather than product demand and are deduped by product "
             "on re-analysis.",
    )
