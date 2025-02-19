# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class AIGenerationParams(models.AbstractModel):
    """Mixin for common AI generation parameters across different providers."""
    _name = 'ai.generation.params'
    _description = 'Common AI Generation Parameters'

    # Basic Generation Parameters
    temperature = fields.Float(
        string='Temperature',
        help='Sampling temperature. Range: [0.0 - 2.0]. Higher values make output more random, lower values more deterministic.',
        default=0.7,
        digits=(3, 2))
    
    top_p = fields.Float(
        string='Top P',
        help='Nucleus sampling: limits cumulative probability of tokens to sample from. Range: [0.0 - 1.0].',
        default=0.9,
        digits=(3, 2))
    
    max_tokens = fields.Integer(
        string='Max Tokens',
        help='Maximum number of tokens to generate. Range: [1 - 32768].',
        default=2048)
    
    stop_sequences = fields.Char(
        string='Stop Sequences',
        help='Comma-separated list of sequences where the model should stop generating')

    # System Settings
    timeout = fields.Integer(
        string='Timeout',
        help='Request timeout in seconds. Range: [1 - 300].',
        default=30)
    
    retry_count = fields.Integer(
        string='Retry Count',
        help='Number of times to retry failed requests. Range: [0 - 5].',
        default=3)
    
    stream_response = fields.Boolean(
        string='Stream Response',
        help='Enable response streaming for real-time output.',
        default=False)

    def _get_base_generation_params(self):
        """Get common generation parameters as a dictionary."""
        self.ensure_one()
        
        params = {
            'temperature': self.temperature,
            'top_p': self.top_p,
            'max_tokens': self.max_tokens,
            'stream': self.stream_response,
        }
        
        if self.stop_sequences:
            params['stop'] = [
                seq.strip() 
                for seq in self.stop_sequences.split(',')
            ]
        
        return params
