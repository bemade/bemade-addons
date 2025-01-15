from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    customer_requisition_ref = fields.Char(
        string='Customer Requisition Ref',
        related='order_id.requisition_id.customer_requisition_ref',
        store=True,
        help='Customer requisition reference'
    )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.customer_requisition_ref:
                if line.name:
                    line.name = f"[{line.customer_requisition_ref}] {line.name}"
        return lines
