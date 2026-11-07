from odoo import api, fields, models


class StockOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    supplier_id = fields.Many2one(
        compute="_compute_supplier_id", store=True, readonly=False
    )

    @api.depends(
        "trigger",
        "product_id",
        "product_id.product_tmpl_id.seller_ids",
        "product_id.product_tmpl_id.seller_ids.sequence",
    )
    def _compute_supplier_id(self):
        """Fill an empty manual line with the product's first vendor price.

        Only ever fills: a vendor already on the line, chosen by hand or filled
        earlier, is kept. Automatic lines are left to Odoo's own choice of
        vendor when it orders.
        """
        for orderpoint in self:
            if orderpoint.supplier_id or orderpoint.trigger != "manual":
                continue
            orderpoint.supplier_id = orderpoint._first_supplier()

    def _first_supplier(self):
        """Return the first current vendor price of the line's product.

        Falls back on the first price of any date when none is current. Prices
        restricted to another company are never used.
        """
        self.ensure_one()
        if not self.product_id:
            return self.env["product.supplierinfo"]
        product = self.product_id.with_company(self.company_id)
        # Both are in vendor-list order and already filtered by company.
        current = product._get_filtered_sellers(quantity=None)
        return (current or product._prepare_sellers())[:1]

    @api.model
    def _fill_missing_supplier(self):
        """Fill the empty manual lines the earlier version left behind."""
        empty = self.search([("trigger", "=", "manual"), ("supplier_id", "=", False)])
        for orderpoint in empty:
            orderpoint.supplier_id = orderpoint._first_supplier()
        return empty
