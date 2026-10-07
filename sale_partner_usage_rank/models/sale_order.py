# Copyright 2026 Bemade Inc. <marc@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, fields, models

from .res_partner import SLOT_RANKS


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # The dropdowns rank by the slot named here (res.partner._order_to_sql).
    # A field's Python context reaches the web client merged under the view's
    # own, so views that redefine the field's context keep it.
    partner_id = fields.Many2one(context={"sale_usage_rank": "partner_id"})
    partner_shipping_id = fields.Many2one(context={"sale_usage_rank": "partner_shipping_id"})
    partner_invoice_id = fields.Many2one(context={"sale_usage_rank": "partner_invoice_id"})

    def _sale_usage_partners(self):
        return self.partner_id | self.partner_shipping_id | self.partner_invoice_id

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._sale_usage_partners()._recount_sale_usage_ranks()
        return orders

    def write(self, vals):
        if not SLOT_RANKS.keys() & vals.keys():
            return super().write(vals)
        before = self._sale_usage_partners()
        res = super().write(vals)
        (before | self._sale_usage_partners())._recount_sale_usage_ranks()
        return res

    def unlink(self):
        partners = self._sale_usage_partners()
        res = super().unlink()
        partners._recount_sale_usage_ranks()
        return res
