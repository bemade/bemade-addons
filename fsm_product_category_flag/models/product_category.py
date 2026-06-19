from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    is_fsm_product = fields.Boolean(
        string='FSM Product',
        help='If enabled, products in this category are considered FSM products and '
             'their sales order lines are included in FSM-related revenue calculations '
             'such as FSM job profitability.'
    )
