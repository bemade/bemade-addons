# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ResCompany(models.Model):
    _inherit = 'res.company'

    openwebui_enabled = fields.Boolean(
        string='Enable OpenWebUI',
        default=False,
        help="Enable integration with OpenWebUI"
    )
    
    openwebui_api_url = fields.Char(
        string='OpenWebUI API URL',
        help="Base URL of the OpenWebUI API (e.g. http://localhost:8080)"
    )
    
    openwebui_api_key = fields.Char(
        string='OpenWebUI API Key',
        help="API key for authentication with OpenWebUI"
    )
    
    openwebui_verify_ssl = fields.Boolean(
        string='Verify SSL Certificate',
        default=True,
        help="Verify the SSL certificate when making API calls"
    )
    
    openwebui_timeout = fields.Integer(
        string='Timeout (seconds)',
        default=30,
        help="Maximum wait time for API calls"
    )

    openwebui_models_ids = fields.One2many(
        comodel_name='openwebui.model',
        inverse_name='company_id',
        string='OpenWebUI Models',
    )

    def test_openwebui_connection(self):
        """Tests the connection to OpenWebUI"""
        self.ensure_one()
        
        if not self.openwebui_enabled:
            raise UserError(_("OpenWebUI is not enabled for this company."))

        model = self.env['openwebui.model'].create({
            'name': 'test_connection',
            'identifier': 'test_connection',
            'company_id': self.id,
            'is_temp': True,
        })
        
        success, message = model.test_connection()
        if not success:
            raise UserError(message)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Connection to OpenWebUI was successful.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def refresh_model_list(self):
        """Refreshes the list of models from OpenWebUI"""
        self.ensure_one()
        
        if not self.openwebui_enabled:
            raise UserError(_("OpenWebUI is not enabled for this company."))

        # Create a temporary model to perform synchronization
        model = self.env['openwebui.model'].create({
            'name': 'refresh_models',
            'identifier': 'refresh_models',
            'company_id': self.id,
            'is_temp': True,
        })
        
        success, message = model.sync_models()
        if not success:
            raise UserError(message)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Model list has been successfully updated.'),
                'type': 'success',
                'sticky': False,
            }
        }
