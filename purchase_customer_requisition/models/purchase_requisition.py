from odoo import models, fields, api

class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    customer_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Customer',
        domain=[('customer_rank', '>', 0)],
        help='Customer for whom this requisition is created'
    )
