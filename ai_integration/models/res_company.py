# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _get_default_provider_instance(self):
        """Get the default AI provider instance from config parameters"""
        provider_id = self.env['ir.config_parameter'].sudo().get_param('ai_integration.default_provider_instance_id')
        return self.env['ai.provider.instance'].browse(int(provider_id)) if provider_id else False

    def _get_default_model(self):
        """Get the default AI model from config parameters"""
        model_id = self.env['ir.config_parameter'].sudo().get_param('ai_integration.default_model_id')
        return self.env['ai.model'].browse(int(model_id)) if model_id else False

    def _get_ai_batch_size(self):
        """Get the AI batch size from config parameters"""
        return int(self.env['ir.config_parameter'].sudo().get_param('ai_integration.ai_batch_size', '100'))
