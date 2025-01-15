from odoo import models, fields, api

class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    customer_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        domain=[('customer_rank', '>', 0)],
        help='Customer for whom this requisition is created'
    )
    
    customer_requisition_ref = fields.Char(
        string='Customer Requisition Ref',
        help='Customer requisition reference'
    )

    def action_in_progress(self):
        res = super().action_in_progress()
        for requisition in self:
            if requisition.customer_requisition_ref:
                # Update all related PO lines description
                for po in requisition.purchase_ids:
                    for line in po.order_line:
                        if line.name and not line.name.startswith(f'[{requisition.customer_requisition_ref}]'):
                            line.name = f'[{requisition.customer_requisition_ref}] {line.name}'
        return res
