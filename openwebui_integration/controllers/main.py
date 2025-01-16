from odoo import http, fields
from odoo.http import request

class OpenWebUIController(http.Controller):
    @http.route('/openwebui/config', type='json', auth='user')
    def get_config(self):
        company = request.env.company
        user_companies = request.env.user.company_ids.ids
        
        return {
            'version': '1.0',
            'enabled': company.openwebui_enabled,
            'company_id': company.id,
            'allowed_company_ids': user_companies,
            'company_name': company.name,
            'model': company.openwebui_model,
            'api_url': company.openwebui_api_url,
            'max_tokens': company.openwebui_max_tokens,
            'temperature': company.openwebui_temperature,
            'timeout': company.openwebui_timeout,
            'use_ssl': company.openwebui_use_ssl,
        }
