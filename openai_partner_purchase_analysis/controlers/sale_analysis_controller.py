from odoo import http
from odoo.http import request

class SaleAnalysisController(http.Controller):
    @http.route('/sale_analysis/render/<int:partner_id>', type='http', auth='user', csrf=False)
    def render_sale_analysis(self, partner_id, **kwargs):
        # Récupérer le partenaire et son contenu d'analyse
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner:
            return request.not_found()

        # Générer le rendu HTML avec les scripts inclus
        sale_analysis_content = partner.sale_analysis or "<p>No analysis available</p>"
        return http.Response(sale_analysis_content, content_type='text/html', status=200)