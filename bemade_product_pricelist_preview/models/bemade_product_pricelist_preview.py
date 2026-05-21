# -*- coding: utf-8 -*-
from odoo import fields, models


class BemadeProductPricelistPreview(models.TransientModel):
    """Transient row holding the computed price for one product/pricelist pair.

    Rows are created on demand by
    ``product.template._compute_computed_pricelist_ids`` (and the
    ``product.product`` variant equivalent) every time the product form is
    opened.  They are vacuumed automatically by Odoo's standard transient-table
    GC (``_transient_max_hours``).
    """

    _name = "bemade.product.pricelist.preview"
    _description = "Product Pricelist Price Preview"
    _order = "sequence, pricelist_id"

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product Template",
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product Variant",
        ondelete="cascade",
    )
    pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        string="Pricelist",
        required=True,
        ondelete="cascade",
    )
    price = fields.Monetary(
        string="Price",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        required=True,
    )
    rule_id = fields.Many2one(
        comodel_name="product.pricelist.item",
        string="Matched Rule",
        ondelete="set null",
    )
    rule_source = fields.Selection(
        selection=[
            ("variant", "Variant Rule"),
            ("template", "Template Rule"),
            ("category", "Category Rule"),
            ("global", "Global Rule"),
            ("formula", "Formula Rule"),
        ],
        string="Rule Type",
    )
    min_quantity = fields.Float(
        string="Min. Qty",
        digits="Product Unit of Measure",
    )
    date_start = fields.Datetime(string="Start Date")
    date_end = fields.Datetime(string="End Date")
    sequence = fields.Integer(
        string="Sequence",
        help="Pricelist sequence used for ordering preview rows.",
    )
