from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_provider_instance_id = fields.Many2one(
        'ai.provider.instance',
        string='Default AI Provider Instance',
        config_parameter='ai_integration.default_provider_instance_id',
        default_model='ai.provider.instance')
    
    default_model_id = fields.Many2one(
        'ai.model',
        string='Default AI Model',
        config_parameter='ai_integration.default_model_id',
        default_model='ai.model')
    
    ai_batch_size = fields.Integer(
        string='AI Batch Processing Size',
        config_parameter='ai_integration.ai_batch_size',
        default=100,
        default_model='ai.provider.instance')
    
    @api.onchange('default_provider_instance_id')
    def _onchange_default_provider_instance(self):
        """Reset model when provider instance changes"""
        if self.default_provider_instance_id:
            self.default_model_id = False
