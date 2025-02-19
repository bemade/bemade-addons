# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AIModel(models.Model):
    _name = 'ai.model'
    _description = 'AI Model'
    _order = 'sequence, name'
    _check_company = False  # Disable automatic company checks

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this model is active and available for use')

    name = fields.Char(
        string='Name',
        required=True,
        help='Name of the AI model'
    )
    
    identifier = fields.Char(
        string='Identifier',
        required=True,
        help='Technical identifier of the model (e.g., gpt-3.5-turbo, mistral-7b)'
    )
    
    provider_instance_id = fields.Many2one(
        'ai.provider.instance',
        string='Provider Instance',
        required=True,
        ondelete='cascade',
        help='Provider instance this model belongs to'
    )
    
    provider_type = fields.Selection(
        related='provider_instance_id.provider_type',
        string='Provider Type',
        store=True,
        readonly=True,
        help='Type of AI provider'
    )
    
    description = fields.Text(
        string='Description',
        help='Description of the model and its capabilities'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Sequence for ordering models in lists and dropdowns'
    )
    
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this model is active'
    )
    
    context_window = fields.Integer(
        string='Context Window',
        default=2048,
        help='Maximum number of tokens in the context window'
    )
    
    _sql_constraints = [
        ('unique_identifier_provider',
         'unique(identifier, provider_instance_id)',
         'The model identifier must be unique per provider instance!')
    ]
    
    def name_get(self):
        """Custom name_get to include provider instance in display name."""
        result = []
        for model in self:
            name = f"{model.name} ({model.provider_instance_id.name})"
            result.append((model.id, name))
        return result
