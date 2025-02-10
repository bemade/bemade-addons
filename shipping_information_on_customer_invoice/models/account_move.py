from odoo import api, fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_delivery_info(self):
        """Get the delivery information for the invoice."""
        self.ensure_one()
        if self.move_type != 'out_invoice':
            return False
        
        deliveries = self.picking_ids.filtered(lambda p: p.carrier_id)
        if not deliveries:
            return False
            
        carrier = deliveries[0].carrier_id
        return {
            'carrier_name': carrier.name,
            'tracking_ref': deliveries[0].carrier_tracking_ref or '',
            'invoice_policy': dict(carrier._fields['invoice_policy'].selection).get(carrier.invoice_policy, carrier.invoice_policy),
        }
