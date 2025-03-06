# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.addons.mail.models.mail_thread import MailThread
from odoo.exceptions import UserError


class BaseAIProviderInstance(models.Model):
    _name = 'ai.provider.instance'
    _description = 'AI Provider Instance'
    _order = 'name'
    _check_company = False  # Disable automatic company checks
    _inherit = ['mail.thread', 'ai.base.mixin']

    @api.model
    def default_get(self, fields_list):
        """Override default_get to prevent creation if no provider modules are installed."""
        defaults = super().default_get(fields_list)
        if defaults.get('provider_type', 'none') == 'none':
            defaults['provider_type'] = 'ollama'
        return defaults

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this provider instance is active and available for use')

    name = fields.Char(
        string='Name',
        required=True,
        help='Name of this provider instance (e.g., "OpenWebUI Production", "Ollama Local")'
    )
    
    provider_type = fields.Selection(
        [('none', 'None')],  # Base selection, will be extended by provider modules
        string='Provider Type',
        required=True,
        default='none',
        help='The type of AI provider for this instance',
        ondelete={'none': lambda r: r.write({'provider_type': 'none'})}
    )
    
    host = fields.Char(
        string='Host',
        required=True,
        help='Host address (e.g., "http://localhost:8080" or "https://api.example.com")'
    )
    
    api_key = fields.Char(
        string='API Key',
        help='API key if required by the provider',
        invisible="[('provider_type', '=', 'ollama')]"  # Hide when provider type is ollama
    )
    
    @api.model
    def get_default_instance(self):
        """Get the default AI provider instance to use.
        
        Returns:
            ai.provider.instance: The default instance to use, or raises UserError if none found
        """
        instance = self.env['ai.provider.instance'].search([('active', '=', True)], limit=1)
        if not instance:
            raise UserError(_('No active AI provider instance found. Please configure one in the settings.'))
        return instance
    
    model_ids = fields.One2many(
        'ai.model',
        'provider_instance_id',
        copy=True,
        string='Available Models'
    )
    
    timeout = fields.Integer(
        string='Timeout',
        default=60,
        help='Maximum wait time for API calls (in seconds)'
    )
    
    max_retries = fields.Integer(
        string='Max Retries',
        default=3,
        help='Maximum number of retry attempts for failed API calls'
    )
    
    @api.model
    def _valid_field_parameter(self, field, name):
        return name == 'invisible' or super()._valid_field_parameter(field, name)
    
    _sql_constraints = [
        ('name_uniq',
         'unique(name)',
         'Provider instance name must be unique!')
    ]
    
    def test_connection(self):
        """Test the connection to this provider instance."""
        self.ensure_one()
        if self.provider_type == 'none':
            raise UserError(_('Please select a provider type'))
        return {'type': 'ir.actions.act_window_close'}
    
    def sync_models(self):
        """Synchronize models from this provider instance."""
        self.ensure_one()
        if self.provider_type == 'none':
            raise UserError(_('Please select a provider type'))
