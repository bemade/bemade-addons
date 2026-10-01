from odoo import fields, models


class ProductCustomerCode(models.Model):
    _name = "product.customer.code"
    _description = "Customer Product Code"
    _rec_name = "product_code"
    _order = "partner_id, product_code, id"

    product_code = fields.Char(
        string="Customer Product Code",
        index="trigram",
        help="The customer's own reference for this product.",
    )
    product_name = fields.Char(
        string="Customer Product Name",
        index="trigram",
        help="The customer's own name for this product.",
    )
    product_id = fields.Many2one(
        "product.template",
        string="Product",
        required=True,
        index=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="product_id.company_id", store=True, index=True
    )
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "UNIQUE(partner_id, product_id)",
        "A customer can only have one code per product.",
    )
