from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"
    _order = "is_favorite desc, default_code, name, id"

    product_customer_code_ids = fields.One2many(
        "product.customer.code",
        "product_id",
        string="Customer Codes",
        copy=False,
    )
