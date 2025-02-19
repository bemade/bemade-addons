# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.addons.mail.models.mail_thread import MailThread
from odoo.exceptions import UserError


class AIProviderInstance(models.Model):
    _name = 'ai.provider.instance'
    _description = 'AI Provider Instance'
    _order = 'name'
    _check_company = False  # Disable automatic company checks
    _inherit = ['mail.thread', 'ai.base.mixin']

    @api.model
    def _has_provider_modules(self):
        """Check if any AI provider modules are installed."""
        modules = ['ollama_ai_integration', 'chatgpt_ai_integration']
        return any(self.env['ir.module.module'].search([('name', 'in', modules), ('state', '=', 'installed')]))

    @api.model
    def default_get(self, fields_list):
        """Override default_get to prevent creation if no provider modules are installed."""
        if not self._has_provider_modules():
            raise UserError(_('No AI provider modules are installed. Please install at least one provider module (e.g., Ollama or ChatGPT) before creating a provider instance.'))
        return super().default_get(fields_list)

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this provider instance is active and available for use')

    name = fields.Char(
        string='Name',
        required=True,
        help='Name of this provider instance (e.g., "OpenWebUI Production", "Ollama Local")'
    )
    
    provider_id = fields.Many2one(
        'ai.provider',
        string='Provider',
        required=True,
        ondelete='restrict',
        help='The AI provider configuration'
    )

    provider_type = fields.Selection(
        selection=[
            ('none', 'None')  # Base selection, will be extended by provider modules
        ],
        string='Provider Type',
        required=True,
        ondelete={'none': 'set default'},
        default='none',
        help='Type of AI provider'
    )
    
    host = fields.Char(
        string='Host',
        required=True,
        help='Host address (e.g., "http://localhost:8080" or "https://api.example.com")'
    )
    
    api_key = fields.Char(
        string='API Key',
        help='API key if required by the provider'
    )
    
    
    @api.onchange('provider_id')
    def _onchange_provider_id(self):
        if self.provider_id:
            self.provider_type = self.provider_id.code
    
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
    
    _sql_constraints = [
        ('name_uniq',
         'unique(name)',
         'Provider instance name must be unique!')
    ]
    
    def test_connection(self):
        """Test the connection to this provider instance."""
        self.ensure_one()
        provider_model = f'ai.provider.{self.provider_type}'
        if provider_model not in self.env:
            raise UserError(_("Provider type %s is not installed", self.provider_type))
            
        return self.env[provider_model].test_connection(self)
    
    def sync_models(self):
        """Synchronize models from this provider instance."""
        self.ensure_one()
        provider_model = f'ai.provider.{self.provider_type}'
        if provider_model not in self.env:
            raise UserError(_("Provider type %s is not installed", self.provider_type))
            
        return self.env[provider_model].sync_models(self)
