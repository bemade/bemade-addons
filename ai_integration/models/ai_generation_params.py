from odoo import models, fields, api, _

class AIGenerationParams(models.AbstractModel):
    _name = 'ai.generation.params'
    _description = 'AI Generation Parameters'

    # Base Generation Parameters
    temperature = fields.Float(
        string='Temperature',
        help='Controls randomness in generation. Higher values make output more random, lower values more deterministic.',
        default=0.7)
    
    repeat_penalty = fields.Float(
        string='Repeat Penalty',
        help='Penalty for repeating tokens. Higher values make repetition less likely.',
        default=1.1)
    
    max_tokens = fields.Integer(
        string='Max Tokens',
        help='Maximum number of tokens to generate.',
        default=2048)
    
    stop_sequences = fields.Char(
        string='Stop Sequences',
        help='Comma-separated list of sequences where generation should stop.',
        default='')
    
    frequency_penalty = fields.Float(
        string='Frequency Penalty',
        help='Penalty for using frequent tokens. Higher values encourage using less frequent tokens.',
        default=0.0)
    
    presence_penalty = fields.Float(
        string='Presence Penalty',
        help='Penalty for using tokens already in the text. Higher values encourage using new tokens.',
        default=0.0)
