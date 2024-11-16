
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    api_key = fields.Char(string="API Key", help="API Key for OpenAI specific to this company. It should start with 'sk-'")
    organization = fields.Char(string="Organization ID", help="Organization ID for OpenAI specific to this company. It should start with 'org-'")
            