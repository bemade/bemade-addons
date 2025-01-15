from odoo import models, fields, api


class PurchaseRequisition(models.Model):
    _inherit = "purchase.requisition"

    customer_ids = fields.Many2many(
        comodel_name="res.partner",
        string="Applicable Customers",
        help="Customer for whom this requisition is applicable",
    )
