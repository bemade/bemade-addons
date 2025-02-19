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
