# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import fields, models


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    param_ids = fields.One2many(
        comodel_name="product.attribute.value.param",
        inverse_name="attribute_value_id",
        string="Parameters",
        help="Named numbers this value contributes to bill-of-materials "
        "quantity expressions.",
    )
