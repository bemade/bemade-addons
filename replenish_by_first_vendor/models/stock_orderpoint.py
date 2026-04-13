from odoo import models, fields, api


class StockOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for orderpoint in res:
            if (
                orderpoint.trigger == "manual"
                and not orderpoint.supplier_id
                and orderpoint.product_id.seller_ids
            ):
                orderpoint.supplier_id = orderpoint.product_id.seller_ids[0]
        return res
