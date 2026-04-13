# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def action_apply_single_inventory(self):
        """
        New method that opens the same reason dialog as action_apply_all
        for single inventory adjustments.
        """
        ctx = dict(self.env.context or {}, default_quant_ids=self.ids)
        view = self.env.ref('stock.stock_inventory_adjustment_name_form_view', False)
        return {
            'name': _('Inventory Adjustment Reference / Reason'),
            'type': 'ir.actions.act_window',
            'views': [(view.id, 'form')],
            'res_model': 'stock.inventory.adjustment.name',
            'target': 'new',
            'context': ctx,
        }
