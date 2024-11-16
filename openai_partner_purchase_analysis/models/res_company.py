from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    product_categories_analyzed = fields.Many2many(
        'product.category',
        string="Product Categories Analyzed",
        help="Select product categories to include in the purchase analysis. Only products in these categories and their subcategories will be analyzed."
    )

