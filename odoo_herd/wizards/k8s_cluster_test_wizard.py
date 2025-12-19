import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class K8sClusterTestWizard(models.TransientModel):
    _name = 'k8s.cluster.test.wizard'
    _description = 'Test Kubernetes Cluster Connection'

    cluster_id = fields.Many2one(
        'k8s.cluster',
        string='Cluster',
        required=True,
        default=lambda self: self.env.context.get('active_id')
    )
    
    test_result = fields.Text(
        string='Test Result',
        readonly=True
    )
    
    state = fields.Selection([
        ('draft', 'Ready to Test'),
        ('testing', 'Testing...'),
        ('done', 'Test Complete'),
    ], default='draft')

    def action_test_connection(self):
        """Test the cluster connection"""
        self.ensure_one()
        
        if not self.cluster_id:
            raise UserError(_('Please select a cluster to test'))
        
        self.state = 'testing'
        
        try:
            # Test the connection
            result = self.cluster_id.test_connection()
            
            # Extract the message from the notification result
            if isinstance(result, dict) and 'params' in result:
                message = result['params'].get('message', 'Test completed')
                test_type = result['params'].get('type', 'info')
                
                if test_type == 'success':
                    self.test_result = f"✓ SUCCESS: {message}"
                else:
                    self.test_result = f"✗ ERROR: {message}"
            else:
                self.test_result = "Test completed successfully"
            
            self.state = 'done'
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'k8s.cluster.test.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': self.env.context,
            }
            
        except Exception as e:
            _logger.error(f"Connection test failed: {e}")
            self.test_result = f"✗ ERROR: {str(e)}"
            self.state = 'done'
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'k8s.cluster.test.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': self.env.context,
            }

    def action_close(self):
        """Close the wizard"""
        return {'type': 'ir.actions.act_window_close'}
