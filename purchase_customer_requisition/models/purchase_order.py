from odoo import models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _merge_alternative_po(self, rfqs):
        """Override to handle requisition_id during merge.
        
        Args:
            rfqs: recordset of purchase.order to merge
            
        Returns:
            purchase.order: the merged purchase order
        """
        # Only merge orders in draft or sent state
        rfqs = rfqs.filtered(lambda o: o.state in ('draft', 'sent'))

        # Get the oldest order as base
        base_order = rfqs.sorted(lambda x: (x.date_order, x.id))[0]
        
        # Call parent method to merge orders
        merged_order = super()._merge_alternative_po(rfqs)

        # After merge, ensure lines are properly linked to their requisitions
        for line in merged_order.order_line:
            line._compute_requisition_id()
            if line.requisition_id and line.requisition_line_id:
                line.price_unit = line.requisition_line_id.price_unit

        return merged_order
