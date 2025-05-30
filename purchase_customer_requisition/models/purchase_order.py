from odoo import models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_merge(self):
        """Override to clear requisition_id before merging multiple POs"""
        if len(self) > 1:
            # Check if all POs have the same requisition_id
            unique_requisitions = set(order.requisition_id.id for order in self if order.requisition_id)
            
            # Only clear requisition_ids if they are different
            if len(unique_requisitions) > 1:
                self.write({'requisition_id': False})
            
            # Call parent method to perform merge
            result = super().action_merge()
            
            return result
            
        return super().action_merge()
