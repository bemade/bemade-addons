from odoo import models, fields, api
from odoo.exceptions import UserError

class AIConfig(models.Model):
    _name = 'ai.config'
    _description = 'AI Configuration'
    _inherit = ['mail.thread']

    name = fields.Char(string='Name', required=True, default='Default Config', tracking=True)
    company_id = fields.Many2one(
        'res.company', 
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    openwebui_url = fields.Char(
        string='Open WebUI URL',
        required=True,
        default='http://localhost:8080',
        tracking=True
    )
    model_name = fields.Char(
        string='Model Name',
        required=True,
        help='Nom du modèle à utiliser dans Open WebUI',
        tracking=True
    )
    system_prompt = fields.Text(
        string='System Prompt',
        default="""Tu es un assistant Odoo expert qui aide les utilisateurs à effectuer des actions 
dans le système. Analyse leurs demandes et propose des actions concrètes.""",
        tracking=True
    )
    temperature = fields.Float(
        string='Temperature',
        default=0.7,
        help='Contrôle la créativité des réponses (0.0 - 1.0)',
        tracking=True
    )
    max_tokens = fields.Integer(
        string='Max Tokens',
        default=2000,
        tracking=True
    )
    active = fields.Boolean(default=True, tracking=True)

    _sql_constraints = [
        ('company_uniq', 'unique(company_id, active)',
         'Une seule configuration active par compagnie est autorisée!')
    ]

    @api.model
    def get_default_config(self):
        """Récupère la configuration active pour la compagnie actuelle"""
        config = self.search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if not config:
            raise UserError('Aucune configuration AI active trouvée pour votre compagnie')
