from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    sale_analysis = fields.Html("Sale Analysis", help="Analysis of the partner's sales.")
    sale_analysis_date = fields.Date("Sale Analysis Date", help="Date of the latest sale analysis.")

    def action_open_purchase_analysis(self):
        """Ouvre le wizard d'analyse des achats pour le client actuel."""
        return {
            'name': 'Purchase Analysis',
            'type': 'ir.actions.act_window',
            'res_model': 'partner.purchase.analysis.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            },
        }