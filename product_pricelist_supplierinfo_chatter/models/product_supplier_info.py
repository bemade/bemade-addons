# -*- coding: utf-8 -*-

from odoo import models, fields, api
from markupsafe import Markup


class ProductSupplierInfo(models.Model):
    _name = "product.supplierinfo"
    _inherit = ["product.supplierinfo", "mail.thread", "mail.activity.mixin"]

    # Commented out because breaking basic Odoo tests. See if this is really needed.

    # _sql_constraints = [("supplierinfo_product_tmpl_id_no_null",
    #                      "CHECK((product_tmpl_id IS NOT NULL))",
    #                      "Supplier pricelist need product template"),
    #                     ]

    # This while avoid the database to save those record with lost product_tmpl_id
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
            rec.supplier_list_price = (100 * rec.price) / (100 - discount)

    # We add tracking to the fields that are displayed in the chatter
    partner_id = fields.Many2one(
        tracking=True, 
        domain=[("is_company", "=", True)]
        )
    
    product_name = fields.Char(tracking=True)
    product_code = fields.Char(tracking=True)
    product_uom = fields.Many2one(tracking=True)
    min_qty = fields.Float(tracking=True)
    currency_id = fields.Many2one(tracking=True)
    date_start = fields.Date(tracking=True)
    date_end = fields.Date(tracking=True)
    product_id = fields.Many2one(tracking=True)
    product_tmpl_id = fields.Many2one(tracking=True)
    delay = fields.Integer(tracking=True)

    date_updated = fields.Date(
        string="Last updated",
        help="Date at which the supplier " + " list price was last updated.",
    )

    purchasing_notes = fields.Text(
        tracking=True, 
        string="Purchasing Notes"
    )

    supplier_list_price = fields.Float(
        string="Supplier List Price",
        digits="Product Price",
        tracking=True,
        help="""This the supplier list price to which supplier discounts are applied, if 
                                               any, and the net price if no supplier discounts are to be applied""",
    )

    supplier_discount_percent = fields.Float(
        string="Supplier discount (%)", 
        digits="Product Price", 
        tracking=True, 
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

    def _generate_chatter(self, vals, operation):
        if len(self) == 1 and self.product_tmpl_id:
            msg = ""
            headmsg = (
                f"<a href='#' data-oe-model='product.supplierinfo' data-oe-id='{self.id}'>"
                f"Price {operation} for {self.product_id.name} : <br /></a>"
            )
            if self.min_qty > 0:
                msg += f"<li>Minimum qty : {self.min_qty}</li>"
            if self.date_start:
                msg += f"<li>Starting : {self.date_start}</li>"
            if self.date_end:
                msg += f"<li>Ending : {self.date_end}</li>"
            if msg:
                msg = headmsg + "<ul>" + msg + "</ul>"
            else:
                msg = headmsg
            for change in vals:
                msg += f"{change} --> {vals[change]}<br />"
            # Should always be there
            if self.product_tmpl_id:
                self.product_tmpl_id.message_post(
                    body=Markup(msg),
                )
            # only for variant
            if self.product_id:
                self.product_id.message_post(body=Markup(msg))

    # Well hard time to set the chatter
    #     def create(self, vals):
    #         res = super(ProductSupplierInfo, self).create(vals)
    # # #        res._generate_chatter(vals, 'create')

    def write(self, vals):
        res = super(ProductSupplierInfo, self).write(vals)
        self._generate_chatter(vals, "modify")
        return res

    def suplierinfo_show_details(self):
        """
        Action to open product.supplierinfo (pricelist) in its own windows and not in a javascript
        popup to avoid loosing product_tmpl_id.  We rely on both context and domain to pass the
        information
        """
        # views = [(self.env.ref('account.invoice_supplier_tree').id, 'tree'),
        #          (self.env.ref('account.invoice_supplier_form').id, 'form')]
        return {
            "name": "Supplier price",
            "view_type": "form",
            "view_mode": "form",
            "res_id": self.id,
            "context": self.env.context,
            "res_model": "product.supplierinfo",
            "domain": [
                ("product_tmpl_id", "=", self.product_tmpl_id),
                ("product_id", "=", self.product_id),
            ],
            "type": "ir.actions.act_window",
            # 'view_id': False,
            # 'views': views,
        }
