from odoo import models, fields, api, _

class AIProviderInstance(models.Model):
    """Extends the AI Provider Instance model to support Ollama-specific configuration.
    
    This model inherits from both ai.provider.instance and ollama.provider.mixin to:
    1. Add Ollama-specific fields (num_ctx, temperature, etc.)
    2. Handle field visibility based on provider_type
    3. Manage field cleanup when switching providers
    
    Note: This extends the base ai.provider.instance model instead of creating
    a new one to ensure seamless integration with the core AI framework.
    """
    _name = 'ai.provider.instance'
    _inherit = ['ollama.provider.mixin', 'mail.thread']
    _description = 'AI Provider Instance'
    
    # Basic Fields
    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
        help='Name of this AI provider instance')
        
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Whether this provider instance is active')
        
    host = fields.Char(
        string='Host',
        required=True,
        default='http://localhost:11434',
        tracking=True,
        help='Ollama server host URL')
        
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company this provider instance belongs to')

    @api.onchange('provider_type')
    def _onchange_provider_type(self):
        """Automatically clear Ollama-specific fields when switching provider type.
        
        This ensures that Ollama configuration is only kept when the provider
        type is 'ollama'. When switching to another provider, all Ollama-specific
        fields are reset to their default values to avoid confusion.
        """
        if self.provider_type != 'ollama':
            self.update({
                'num_ctx': False,  # Context length
                'temperature': False,  # Sampling temperature
                'top_p': False,  # Nucleus sampling threshold
                'top_k': False,  # Top-k sampling threshold
                'repeat_penalty': False,  # Penalty for repeated tokens
            })

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
            self.env['ai.provider.ollama']._get_models(self)
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
            provider = self.env['ai.provider.ollama']
            models = provider._get_models(self)
            
            for model_data in models:
                # Create or update AI model record
                self.env['ai.model'].create_or_update({
                    'name': model_data['name'],
                    'identifier': model_data['id'],
                    'provider_instance_id': self.id,
                    'model_type': 'text',
                    'active': True,
                })
                
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Successfully synchronized %d models', len(models)),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_('Model synchronization failed: %s', str(e)))
