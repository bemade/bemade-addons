# -*- coding: utf-8 -*-
"""OpenWebUI Product Integration Module

This module extends product.template functionality to integrate
OpenWebUI artificial intelligence into product management.
It enables automatic product category suggestions
based on description and characteristics analysis.

Main features:
- AI-powered category suggestions
- Suggestion history tracking
- Integrated user interface
"""

import json
import logging
from datetime import datetime

from odoo import models, fields, _
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.addons.openwebui_integration.models.openwebui_bot_mixin import OpenWebUIBotMixin

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model, OpenWebUIBotMixin):
    _inherit = "product.template"

    suggested_category_id = fields.Many2one(
        comodel_name='product.category',
        string="Suggested Category",
        readonly=True,
        help="Category suggested by AI based on product information analysis"
    )

    suggestion_confidence = fields.Float(
        string="Confidence", 
        readonly=True,
        help="Confidence score (0-100) indicating how sure the AI is about the suggested category"
    )

    suggestion_date = fields.Datetime(
        string="Suggestion Date", 
        readonly=True,
        help="Date and time when the category was suggested by the AI"
    )
    
    suggestion_history_ids = fields.One2many(
        comodel_name='product.category.suggestion.history', 
        inverse_name='product_id',
        string="Suggestion History",
        help="History of all category suggestions made by AI for this product"
    )

    def _generate_bot_message(self, records, values, command=None):
        """Generates the message to send to the bot to get category suggestions."""
        # Préparer les données des produits
        products_data = [{
            'odoo_id': record.id,  # ID interne Odoo
            'name': record.name,
            'description': record.description or '',
            'description_sale': record.description_sale or '',
            'default_code': record.default_code or '',
            'current_category': record.categ_id.display_name,
            'sellers': [
                {
                    'name': seller.partner_id.display_name,
                    'product_code': seller.product_code or '',
                    'product_name': seller.product_name or ''
                } for seller in record.seller_ids
            ]
        } for record in records]

        # Récupérer toutes les catégories disponibles
        Category = self.env['product.category']
        categories = Category.search([('parent_id', '!=', False)], order='complete_name')
        available_categories = [{
            'id': cat.id,
            'name': cat.name,
            'complete_name': cat.complete_name or cat.name,
            'level': len(cat.parent_path.split('/')) - 1 if cat.parent_path else 0
        } for cat in categories]

        # Construire le message pour l'IA
        message = {
            'task': 'product_categorization',
            'products': products_data,
            'available_categories': available_categories,
            'instructions': """For each product in the products list, analyze the product information and suggest the most appropriate product category from the available list.
            Consider each product's name, description, and supplier information to make the best match.
            Return a list of JSON objects, one for each product, with:
            - 'odoo_id' (integer): The internal Odoo ID of the product
            - 'category_id' (integer): The ID of the most appropriate category
            - 'confidence' (float between 0 and 100): How confident you are about this suggestion
            - 'explanation' (string): A detailed explanation of why this category was chosen, including analysis of the product name, description, and other relevant information.""",
            'format': 'json'
        }
        return json.dumps(message)

    def _process_bot_response(self, values, response):
        """Process the bot response to extract the suggested category."""
        try:
            results = json.loads(response)
            if not isinstance(results, list):
                raise ValueError("La réponse n'est pas une liste JSON valide")

            for result in results:
                category_id = result.get('category_id')
                confidence = result.get('confidence', 0.0)
                product_id = result.get('odoo_id')

                if not category_id:
                    raise ValueError("No category ID in response")

                if not product_id:
                    raise ValueError("No product ID in response")

                # Vérifier que la catégorie existe
                category = self.env['product.category'].browse(category_id).exists()
                if not category:
                    raise ValueError(f"Category {category_id} not found")

                # Trouver le produit concerné
                product = self.filtered(lambda p: p.id == product_id)
                if not product:
                    raise ValueError(f"Product {product_id} not found in selection")

                # Mettre à jour les valeurs pour ce produit
                product.write({
                    'suggested_category_id': category_id,
                    'suggestion_confidence': confidence,
                    'suggestion_date': fields.Datetime.now(),
                })

                # Créer l'historique
                self.env['product.category.suggestion.history'].create({
                    'product_id': product_id,
                    'suggested_category_id': category_id,
                    'suggestion_confidence': confidence,
                    'input_data': json.dumps(result),
                    'explanation': result.get('explanation', ''),
                    'applied': False
                })

        except Exception as e:
            raise UserError(_("Erreur lors du traitement de la réponse de l'IA: %s") % str(e))

        return values

    def action_suggest_category(self):
        """Request category suggestions from AI."""
        if len(self) > 800:
            raise UserError(_("For performance reasons, you cannot analyze more than 800 products at once."))

        # Get company settings
        company = self.env.company
        if not company.openwebui_enabled:
            raise UserError(_("OpenWebUI is not enabled for your company. Please enable it in company settings."))
            
        model = company.openwebui_default_model_id
        if not model:
            raise UserError(_("No default OpenWebUI model configured. Please configure it in company settings."))

        # Process products in batches
        batch_size = company.openwebui_products_per_request
        successful_products = self.env['product.template']
        
        for i in range(0, len(self), batch_size):
            batch = self[i:i + batch_size]
            
            # Créer une nouvelle transaction pour ce batch
            with self.env.cr.savepoint():
                try:
                    values = {'bot': model}
                    self._apply_logic(batch, values)
                    # Si on arrive ici, le batch a réussi
                    successful_products |= batch
                    _logger.info('Successfully processed batch of %d products: %s', 
                                len(batch), batch.mapped('default_code'))
                except Exception as e:
                    _logger.error('Batch processing failed for products %s: %s', 
                                 batch.mapped('default_code'), str(e))
                    # Le savepoint sera rollback automatiquement
                    continue

        # Si aucun produit n'a été traité avec succès
        if not successful_products:
            raise UserError(_('No suggestions could be generated by AI.'))

        # Ouvrir l'assistant si des suggestions ont été générées
        if any(product.suggested_category_id for product in successful_products):
            wizard = self.env['product.category.suggestion.wizard'].create({})
            return {
                'name': _('Category Suggestions'),
                'type': 'ir.actions.act_window',
                'res_model': 'product.category.suggestion.wizard',
                'res_id': wizard.id,
                'view_mode': 'form',
                'target': 'new',
                'context': self.env.context,
            }
        else:
            raise UserError(_('No valid suggestions could be generated by AI.'))