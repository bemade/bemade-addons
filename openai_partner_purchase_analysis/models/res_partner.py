from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    sale_analysis = fields.Html("Sale Analysis", help="Analysis of the partner's sales.")
    sale_analysis_date = fields.Date("Sale Analysis Date", help="Date of the latest sale analysis.")
    sale_analysis_url = fields.Char(string="Sale Analysis URL", compute="_compute_sale_analysis_url")

    sale_analysis_iframe = fields.Html(string="Sale Analysis Iframe", compute="_compute_sale_analysis_iframe")

    def _compute_sale_analysis_iframe(self):
        for partner in self:
            # Construction de l'iframe directement dans le champ HTML
            partner.sale_analysis_iframe = f"""
            <iframe 
                src="/sale_analysis/render/{partner.id}" 
                width="100%" height="600px" frameborder="0">
            </iframe>
            """

    def _compute_sale_analysis_url(self):
        for partner in self:
            partner.sale_analysis_url = f'/sale_analysis/render/{partner.id}'

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