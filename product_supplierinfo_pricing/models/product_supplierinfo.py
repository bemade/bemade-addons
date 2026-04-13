# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductSupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    date_updated = fields.Date(
        string="Last updated",
        help="Date at which the supplier list price was last updated.",
    )

    purchasing_notes = fields.Text(
        string="Purchasing Notes"
    )

    supplier_list_price = fields.Float(
        string="Supplier List Price",
        digits="Product Price",
        help="""This the supplier list price to which supplier discounts are applied, if 
                                               any, and the net price if no supplier discounts are to be applied""",
    )

    supplier_discount_percent = fields.Float(
        string="Supplier discount (%)", 
        digits="Product Price", 
        default=0
    )

    price = fields.Float(
        compute="_compute_price",
        inverse="_inverse_price",
        string="Supplier Price",
        digits="Product Price",
        help="This price will be considered as a price for the supplier UoM if any or "
        "the default Unit of Measure of the product otherwise",
        store=True,
    )

    @api.depends("supplier_list_price", "supplier_discount_percent")
    def _compute_price(self):
        for rec in self:
            rec.price = rec.supplier_list_price - (
                rec.supplier_list_price * rec.supplier_discount_percent / 100
            )

    @api.depends("supplier_discount_percent")
    def _inverse_price(self):
        for rec in self:
            discount = (
                rec.supplier_discount_percent if rec.supplier_discount_percent else 0
            )
            if discount >= 100:
                rec.supplier_list_price = 0
            else:
                rec.supplier_list_price = (100 * rec.price) / (100 - discount)
