from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests

class OllamaAIProviderInstance(models.Model):
    """Extends the AI Provider Instance model to support Ollama-specific configuration.
    
    This model inherits from both ai.provider.instance and ollama.provider.mixin to:
    1. Add Ollama-specific fields (num_ctx, temperature, etc.)
    2. Handle field visibility based on provider_type
    3. Manage field cleanup when switching providers
    """
    _inherit = ['ai.provider.instance', 'ollama.provider.mixin']
    _name = 'ai.provider.instance'
    _description = 'Ollama AI Provider Instance'

    # Override provider_type to add Ollama option
    provider_type = fields.Selection(
        selection_add=[('ollama', 'Ollama')],
        ondelete={'ollama': lambda r: r.write({'provider_type': 'none'})}
    )
    
    @api.onchange('provider_type')
    def _onchange_provider_type(self):
        """Handle provider type changes.
        
        When switching to 'ollama':
        - Set default host if empty
        
        When switching away from 'ollama':
        - Clear Ollama-specific fields
        """
        if self.provider_type == 'ollama':
            if not self.host:
                self.host = 'http://localhost:11434'
        else:
            # Clear Ollama-specific fields
            self.update({
                'num_ctx': False,  # Context length
                'temperature': False,  # Sampling temperature
                'top_p': False,  # Nucleus sampling threshold
                'top_k': False,  # Top-k sampling threshold
                'repeat_penalty': False,  # Penalty for repeated tokens
                'repeat_last_n': False,  # Number of tokens to consider for repeat penalty
                'num_thread': False,  # Number of CPU threads to use
                'num_gpu': False,  # Number of GPUs to use
                'num_batch': False,  # Batch size for inference
                'model_name': False,  # Model name/path
            })
    
    # Override default host for Ollama
    host = fields.Char(
        default='http://localhost:11434',
        help='Ollama server host URL')

    def test_connection(self):
        """Test the connection to the Ollama server.
        
        This method attempts to connect to the Ollama server and verify
        that it is responding correctly. It will raise a user-friendly
        error if the connection fails.
        
        Returns:
            dict: Action to display success message
        """
        self.ensure_one()
        if self.provider_type != 'ollama':
            return
            
        try:
            # Try to list models as a basic connectivity test
            response = requests.get(f'{self.host}/api/tags')
            response.raise_for_status()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Successfully connected to Ollama server'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_('Connection test failed: %s', str(e)))

    def sync_models(self):
        """Synchronize available models from the Ollama server.
        
        This method fetches the list of available models from the Ollama
        server and creates or updates the corresponding AI model records
        in Odoo.
        
        Returns:
            dict: Action to display success message
        """
        self.ensure_one()
        if self.provider_type != 'ollama':
            return
            
        try:
            # Get models from Ollama API
            response = requests.get(f'{self.host}/api/tags')
            response.raise_for_status()
            
            # Parse response
            models = [{
                'name': model['name'],
                'id': model['name'],
            } for model in response.json()['models']]
            
            for model_data in models:
                # Create or update AI model record
                vals = {
                    'name': model_data['name'],
                    'identifier': model_data['id'],
                    'provider_instance_id': self.id,
                    'active': True,
                }
                # Search for existing model
                existing = self.env['ai.model'].search([
                    ('identifier', '=', model_data['id']),
                    ('provider_instance_id', '=', self.id)
                ], limit=1)
                
                if existing:
                    existing.write(vals)
                else:
                    self.env['ai.model'].create(vals)
            
            # Invalidate the cache to force reload of related records
            self.invalidate_recordset(['model_ids'])
            
            # Return action to reload the view completely
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ai.provider.instance',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
                'flags': {
                    'mode': 'readonly',
                    'reload': True,  # Force reload
                },
                'context': {'notification': {
                    'type': 'success',
                    'title': _('Success'),
                    'message': _('Successfully synchronized %d models', len(models)),
                    'sticky': False,
                }}
            }
        except Exception as e:
            raise UserError(_('Model synchronization failed: %s', str(e)))
