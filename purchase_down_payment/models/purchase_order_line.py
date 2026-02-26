#
#    Bemade Inc.
#
#    Copyright (C) 2025 Bemade Inc. (<https://www.bemade.org>).
#    Author: Bemade Dev Team
#
#    This program is under the terms of the GNU Lesser General Public License,
#    version 3.
#
from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    is_downpayment = fields.Boolean(
        string="Is a down payment",
        help="Down payments are made when creating Bills from a purchase "
             "order. They are not copied when duplicating a purchase order.")

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        res = {
            'display_type': 'product',
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            'price_unit': self.price_unit,
            'purchase_line_id': self.id,
        }
        if optional_values:
            res.update(optional_values)
        if self.display_type:
            res['account_id'] = False
        return res
