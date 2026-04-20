# Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.depends("partner_id")
    def _compute_partner_invoice_id(self):
        for order in self:
            if not order.partner_id:
                order.partner_invoice_id = False
                continue
            ranked = order.partner_id._get_ranked_address_ids("invoice")
            order.partner_invoice_id = ranked[0] if ranked else False

    @api.depends("partner_id")
    def _compute_partner_shipping_id(self):
        for order in self:
            if not order.partner_id:
                order.partner_shipping_id = False
                continue
            ranked = order.partner_id._get_ranked_address_ids("delivery")
            order.partner_shipping_id = ranked[0] if ranked else False
