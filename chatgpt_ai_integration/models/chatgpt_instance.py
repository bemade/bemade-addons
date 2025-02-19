# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ChatGPTInstance(models.Model):
    _name = 'chatgpt.ai.instance'
    _description = 'ChatGPT-Compatible Instance Configuration'
    _inherit = ['ai.provider.instance', 'ai.generation.params']

    provider_type = fields.Selection(
        selection_add=[('chatgpt', 'ChatGPT-Compatible')],
        ondelete={'chatgpt': 'cascade'})
    
    # ChatGPT API Parameters
    
    presence_penalty = fields.Float(
        string='Presence Penalty',
        help='Penalty for new tokens based on their presence in text. Range: [-2.0 - 2.0].',
        default=0.0,
        digits=(3, 2))
    
    frequency_penalty = fields.Float(
        string='Frequency Penalty',
        help='Penalty for new tokens based on their frequency in text. Range: [-2.0 - 2.0].',
        default=0.0,
        digits=(3, 2))
    
    # Provider Settings

    def _get_provider_options(self):
        """Get ChatGPT-compatible options for API calls."""
        self.ensure_one()
        
        options = {
            'temperature': self.temperature,
            'top_p': self.top_p,
            'max_tokens': self.max_tokens,
            'presence_penalty': self.presence_penalty,
            'frequency_penalty': self.frequency_penalty,
            'stream': self.stream_response,
        }
        
        if self.stop_sequences:
            options['stop'] = [
                seq.strip() 
                for seq in self.stop_sequences.split(',')
            ]
        
        return options
