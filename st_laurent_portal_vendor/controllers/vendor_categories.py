# -*- coding: utf-8 -*-

import base64
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError

class VendorProductCategoriesController(http.Controller):
    """
    Contrôleur pour gérer les catégories et tags des produits vendeur
    """
    
    @http.route(['/my/products/<model("vendor.product"):product_id>/categories'], type='http', auth="user", website=True)
    def vendor_product_categories_form(self, product_id=None, **kw):
        """
        Affiche le formulaire de gestion des catégories et tags pour un produit vendeur
        """
        try:
            if not product_id:
                return request.redirect('/my/products')
                
            product_sudo = product_id.sudo()
            # Vérifier que l'utilisateur a accès à ce produit
            if product_sudo.partner_id.id != request.env.user.partner_id.commercial_partner_id.id:
                return request.redirect('/my/products')
            
            # Récupérer toutes les catégories et tags disponibles
            categories = request.env['product.public.category'].sudo().search([])
            tags = request.env['product.tag'].sudo().search([])
            
            # Récupérer les catégories et tags sélectionnés pour ce produit
            selected_category_ids = product_sudo.public_categ_ids.ids
            selected_tag_ids = product_sudo.product_tag_ids.ids
            
            values = {
                'vendor_product': product_sudo,
                'page_name': _('Gérer les catégories et tags'),
                'categories': categories,
                'tags': tags,
                'selected_category_ids': selected_category_ids,
                'selected_tag_ids': selected_tag_ids,
                'error': kw.get('error'),
                'success': kw.get('success'),
            }
            return request.render("st_laurent_portal_vendor.vendor_product_categories_form", values)
        except AccessError:
            return request.redirect('/my/products')

    @http.route(['/my/products/update_categories'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def vendor_product_update_categories(self, **kw):
        """
        Traite la mise à jour des catégories et tags pour un produit vendeur
        """
        product_id = kw.get('product_id')
        if not product_id:
            return request.redirect('/my/products')
        
        try:
            product = request.env['vendor.product'].sudo().browse(int(product_id))
            # Vérifier que l'utilisateur a accès à ce produit
            if product.partner_id.id != request.env.user.partner_id.commercial_partner_id.id:
                return request.redirect('/my/products')
            
            # Récupérer les catégories et tags sélectionnés
            category_ids = request.httprequest.form.getlist('category_ids')
            tag_ids = request.httprequest.form.getlist('tag_ids')
            
            # Si les valeurs ne sont pas des listes, les convertir
            if not isinstance(category_ids, list):
                category_ids = [category_ids] if category_ids else []
            if not isinstance(tag_ids, list):
                tag_ids = [tag_ids] if tag_ids else []
            
            # Convertir en entiers
            category_ids = [int(id) for id in category_ids if id and str(id).isdigit()]
            tag_ids = [int(id) for id in tag_ids if id and str(id).isdigit()]
            
            # Mettre à jour les catégories et tags du produit
            product.write({
                'public_categ_ids': [(6, 0, category_ids)],
                'product_tag_ids': [(6, 0, tag_ids)],
            })
            
            # Rediriger vers la page du produit avec un message de succès
            return request.redirect('/my/products/%s?success=%s' % (
                product.id, 
                _('Les catégories et tags ont été mis à jour avec succès.')
            ))
            
        except Exception as e:
            # En cas d'erreur, rediriger vers le formulaire avec un message d'erreur
            return request.redirect('/my/products/%s/categories?error=%s' % (
                product_id, 
                _("Une erreur est survenue lors de la mise à jour des catégories et tags: %s") % str(e)
            ))
