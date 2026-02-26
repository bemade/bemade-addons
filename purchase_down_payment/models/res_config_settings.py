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


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    po_deposit_default_product_id = fields.Many2one(
        'product.product',
        string='PO Deposit Product',
        domain="[('type', '=', 'service')]",
        config_parameter='purchase_down_payment.po_deposit_default_product_id',
        help='Default product used for payment advances in purchase order')
