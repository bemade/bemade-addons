from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

class CategorySuggestionWizard(models.TransientModel):
    _name = 'product.category.suggestion.wizard'
    _description = 'Assistant de suggestions de catégories'

    product_suggestion_ids = fields.One2many('product.category.suggestion.wizard.line', 'wizard_id', 
                                           string='Suggestions de produits')

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        context = self.env.context
        if context.get('active_model') == 'product.template' and context.get('active_ids'):
            products = self.env['product.template'].browse(context['active_ids'])
            suggestion_lines = []
            for product in products:
                if product.suggested_category_id:
                    suggestion_lines.append((0, 0, {
                        'product_id': product.id,
                        'current_category_id': product.categ_id.id,
                        'suggested_category_id': product.suggested_category_id.id,
                        'confidence': product.suggestion_confidence,
                        'apply_suggestion': False
                    }))
            res['product_suggestion_ids'] = suggestion_lines
        return res

    def action_apply_selected_suggestions(self):
        """Applique les suggestions sélectionnées aux produits."""
        selected_lines = self.product_suggestion_ids.filtered(lambda l: l.apply_suggestion)
        if not selected_lines:
            raise UserError(_('Veuillez sélectionner au moins une suggestion à appliquer.'))

        for line in selected_lines:
            # Mise à jour du produit
            line.product_id.write({
                'categ_id': line.suggested_category_id.id
            })
            
            # Mise à jour de l'historique
            history = self.env['product.category.suggestion.history'].search([
                ('product_id', '=', line.product_id.id),
                ('suggested_category_id', '=', line.suggested_category_id.id)
            ], limit=1)
            if history:
                history.write({'applied': True})

        # Message de confirmation
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('%d catégories ont été mises à jour.') % len(selected_lines),
                'type': 'success',
                'sticky': False,
            }
        }


class CategorySuggestionWizardLine(models.TransientModel):
    _name = 'product.category.suggestion.wizard.line'
    _description = 'Ligne de suggestion de catégorie'
    _order = 'confidence desc, product_id'

    wizard_id = fields.Many2one('product.category.suggestion.wizard', string='Assistant')
    product_id = fields.Many2one('product.template', string='Produit', required=True, readonly=True)
    current_category_id = fields.Many2one('product.category', string='Catégorie actuelle', readonly=True)
    suggested_category_id = fields.Many2one('product.category', string='Catégorie suggérée', readonly=True)
    confidence = fields.Float(string='Confiance (%)', readonly=True)
    apply_suggestion = fields.Boolean(string='Appliquer', default=False)
