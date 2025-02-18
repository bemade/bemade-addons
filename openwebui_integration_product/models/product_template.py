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
        # Prepare product data for AI analysis
        products_data = []
        for record in records:
            products_data.append({
                'odoo_id': record.id,  # Unique Odoo product ID
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
            })

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
            
            IMPORTANT: Your response MUST be a JSON object with a 'products' array containing EXACTLY ONE object for EACH product in the input list.
            Example format for a list of 2 products:
            {
                "products": [
                    {
                        "odoo_id": 1,
                        "category_id": 454,
                        "confidence": 85.0,
                        "explanation": "The product is categorized as safety equipment because..."
                    },
                    {
                        "odoo_id": 2,
                        "category_id": 448,
                        "confidence": 90.0,
                        "explanation": "This product belongs to vacuum systems because..."
                    }
                ]
            }
            
            Requirements:
            1. Response must be a single JSON object with a 'products' array
            2. You MUST return exactly one object in the products array for each product in the input list
            3. Each object must have exactly these fields:
               - odoo_id (integer): The index of the product in the input list (starting at 1)
               - category_id (integer): The ID of the most appropriate category
               - confidence (float between 0 and 100): How confident you are about this suggestion
               - explanation (string): A detailed explanation of why this category was chosen
            4. Do not add any other fields outside of the products array
            5. Do not add any markdown formatting or code blocks
            6. If you're not sure about a product's category, still provide a suggestion with lower confidence""",
            'format': 'json'
        }
        return json.dumps(message)

    def _process_bot_response(self, values, response):
        """Process the bot response to extract the suggested category."""
        try:
            # Parse the response
            if isinstance(response, str):
                response_data = json.loads(response)
            else:
                response_data = response  # Already parsed JSON
                
            # Extract products list
            if isinstance(response_data, dict) and 'products' in response_data:
                results = response_data['products']
            elif isinstance(response_data, list):
                results = response_data
            else:
                raise ValueError("La réponse ne contient pas de liste de produits valide")
                
            if not isinstance(results, list):
                raise ValueError("La réponse n'est pas une liste JSON valide")

            for result in results:
                category_id = result.get('category_id')
                confidence = result.get('confidence', 0.0)
                temp_id = result.get('odoo_id')

                if not category_id:
                    raise ValueError("No category ID in response")

                if not temp_id:
                    raise ValueError("No product ID in response")

                # Vérifier que la catégorie existe
                category = self.env['product.category'].browse(category_id).exists()
                if not category:
                    raise ValueError(f"Category {category_id} not found")

                # Trouver le produit concerné directement par son ID
                product = self.filtered(lambda p: p.id == temp_id)
                if not product:
                    raise ValueError(f"Product {temp_id} not found in selection")

                # Mettre à jour les valeurs pour ce produit
                product.write({
                    'suggested_category_id': category_id,
                    'suggestion_confidence': confidence,
                    'suggestion_date': fields.Datetime.now(),
                })

                # Créer l'historique
                self.env['product.category.suggestion.history'].create({
                    'product_id': product.id,
                    'suggested_category_id': category_id,
                    'suggestion_confidence': confidence,
                    'input_data': json.dumps(result),
                    'explanation': result.get('explanation', ''),
                    'applied': False
                })

        except Exception as e:
            raise UserError(_("Erreur lors du traitement de la réponse de l'IA: %s") % str(e))

        return values

    def _calculate_optimal_batch_size(self, products, max_chars=2048):
        """Calculate the optimal batch size based on message length limit.
        
        Args:
            products: recordset of products to process
            max_chars: maximum number of characters allowed (default: 2048)
            
        Returns:
            int: optimal number of products to process in one batch
        """
        # Test with a small batch first
        test_size = 5
        test_products = products[:test_size]
        test_message = self._generate_bot_message(test_products, {})
        
        # Calculate average characters per product
        chars_per_product = len(test_message) / test_size
        
        # Calculate optimal batch size with 10% safety margin
        optimal_size = int((max_chars * 0.9) / chars_per_product)
        
        # Ensure batch size is at least 1 and no more than 800 (existing limit)
        return max(1, min(optimal_size, 800))

    def action_suggest_category(self):
        """Request category suggestions from AI."""
        # Get company settings
        company = self.env.company
        
        # Dédoublonner les produits
        unique_products = self.filtered(lambda p: p.id).sorted(lambda p: p.id)
        
        # Get max products from company settings
        max_products = company.openwebui_max_products
        
        if len(unique_products) > max_products:
            raise UserError(_("For performance reasons, you cannot analyze more than %d products at once.") % max_products)

        # Get company settings
        company = self.env.company
        if not company.openwebui_enabled:
            raise UserError(_("OpenWebUI is not enabled for your company. Please enable it in company settings."))
            
        model = company.openwebui_default_model_id
        if not model:
            raise UserError(_("No default OpenWebUI model configured. Please configure it in company settings."))

        # Calculate optimal batch size
        batch_size = self._calculate_optimal_batch_size(unique_products)
        _logger.info(f"Processing products with calculated batch size: {batch_size}")
        
        successful_products = self.env['product.template']
        products_to_process = unique_products
        
        for i in range(0, len(products_to_process), batch_size):
            batch = products_to_process[i:i + batch_size]
            
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