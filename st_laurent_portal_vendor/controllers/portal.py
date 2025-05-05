# -*- coding: utf-8 -*-

import base64
import werkzeug

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager


class VendorRequestPortal(CustomerPortal):
    """
    Contrôleur pour gérer les demandes de vendeur dans le portail
    """
    
    @http.route(['/my/vendor/request/new'], type='http', auth="user", website=True)
    def vendor_request_form(self, **kw):
        """
        Affiche le formulaire de demande pour devenir vendeur
        """
        user = request.env.user
        partner = user.partner_id
        
        # Vérifier que l'utilisateur n'est pas déjà un vendeur
        if hasattr(partner, 'is_vendor') and partner.is_vendor:
            return request.redirect('/my/home')
        
        # Vérifier qu'il n'y a pas déjà une demande en attente
        if hasattr(partner, 'has_pending_vendor_request') and partner.has_pending_vendor_request:
            return request.redirect('/my/vendor/requests')
        
        # Récupérer les pays et états autorisés selon la configuration
        config_settings = request.env['res.config.settings'].sudo()
        countries = config_settings.get_allowed_countries()
        states = config_settings.get_allowed_states()
        
        # Déterminer le pays par défaut (Canada si dispo)
        default_country = None
        for country in countries:
            if country.code == 'CA':
                default_country = country
                break
        # Si l'utilisateur a déjà sélectionné un pays, le garder, sinon mettre Canada par défaut
        company_country_id = int(kw.get('company_country_id')) if kw.get('company_country_id') and str(kw.get('company_country_id')).isdigit() else (default_country.id if default_country else False)
        company_state_id = int(kw.get('company_state_id')) if kw.get('company_state_id') and str(kw.get('company_state_id')).isdigit() else False
        # Préremplir les champs société avec le parent si présent
        parent = partner.parent_id or partner.commercial_partner_id if partner.commercial_partner_id != partner else None
        if parent:
            if not kw.get('company_name'):
                kw['company_name'] = parent.name
            if not kw.get('company_street'):
                kw['company_street'] = parent.street
            if not kw.get('company_street2'):
                kw['company_street2'] = parent.street2
            if not kw.get('company_zip'):
                kw['company_zip'] = parent.zip
            if not kw.get('company_city'):
                kw['company_city'] = parent.city
            if not kw.get('company_state_id'):
                kw['company_state_id'] = parent.state_id.id if parent.state_id else False
            if not kw.get('company_country_id'):
                kw['company_country_id'] = parent.country_id.id if parent.country_id else False
            if not kw.get('company_email'):
                kw['company_email'] = parent.email
            if not kw.get('company_phone'):
                kw['company_phone'] = parent.phone
            if not kw.get('company_website'):
                kw['company_website'] = parent.website
            if not kw.get('company_vat'):
                kw['company_vat'] = parent.vat
        values = {
            'page_name': 'vendor_request_new',
            'countries': countries,
            'states': states,
            'partner': partner,
            'company_country_id': company_country_id,
            'company_state_id': company_state_id,
            'error': kw.get('error'),
            'error_message': kw.get('error_message'),
            # Champs préremplis
            'company_name': kw.get('company_name'),
            'company_street': kw.get('company_street'),
            'company_street2': kw.get('company_street2'),
            'company_zip': kw.get('company_zip'),
            'company_city': kw.get('company_city'),
            'company_state_id': kw.get('company_state_id'),
            'company_country_id': kw.get('company_country_id'),
            'company_email': kw.get('company_email'),
            'company_phone': kw.get('company_phone'),
            'company_website': kw.get('company_website'),
            'company_vat': kw.get('company_vat'),
            'description': kw.get('description'),
        }
        return request.render("st_laurent_portal_vendor.portal_vendor_request_form", values)
    
    @http.route(['/my/vendor/request/submit'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def vendor_request_submit(self, **kw):
        """
        Traite la soumission du formulaire de demande pour devenir vendeur
        """
        user = request.env.user
        partner = user.partner_id
        
        # Vérifier que l'utilisateur n'est pas déjà un vendeur
        if hasattr(partner, 'is_vendor') and partner.is_vendor:
            return request.redirect('/my/home')
        
        # Vérifier qu'il n'y a pas déjà une demande en attente
        if hasattr(partner, 'has_pending_vendor_request') and partner.has_pending_vendor_request:
            return request.redirect('/my/vendor/requests')
        
        # Valider les données du formulaire
        if not kw.get('company_name'):
            return self.vendor_request_form(error="missing", error_message=_("Le nom de l'entreprise est obligatoire."))
        
        # Créer la demande
        try:
            vals = {
                'company_name': kw.get('company_name', ''),
                'company_street': kw.get('company_street', ''),
                'company_street2': kw.get('company_street2', ''),
                'company_zip': kw.get('company_zip', ''),
                'company_city': kw.get('company_city', ''),
                'company_state_id': int(kw.get('company_state_id', '0')) if kw.get('company_state_id') and str(kw.get('company_state_id')).isdigit() else False,
                'company_country_id': int(kw.get('company_country_id', '0')) if kw.get('company_country_id') and str(kw.get('company_country_id')).isdigit() else False,
                'company_email': kw.get('company_email', ''),
                'company_phone': kw.get('company_phone', ''),
                'company_website': kw.get('company_website', ''),
                'company_vat': kw.get('company_vat', ''),
                'description': kw.get('description', ''),
            }
            
            vendor_request = request.env['vendor.request'].sudo().create(vals)
            
            # Soumettre la demande
            vendor_request.action_submit()
            
            return request.redirect('/my/vendor/requests')
            
        except Exception as e:
            return self.vendor_request_form(error="error", error_message=str(e))
    
    def _prepare_home_portal_values(self, counters):
        """
        Ajoute le compteur de demandes de vendeur aux valeurs du portail
        """
        values = super(VendorRequestPortal, self)._prepare_home_portal_values(counters)
        
        if 'vendor_request_count' in counters:
            partner = request.env.user.partner_id
            vendor_request_count = request.env['vendor.request'].sudo().search_count([
                ('partner_id', '=', partner.id)
            ])
            values['vendor_request_count'] = vendor_request_count
            
        return values
    
    @http.route(['/my/vendor/requests'], type='http', auth="user", website=True)
    def vendor_requests(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        """
        Affiche la liste des demandes de vendeur de l'utilisateur
        """
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        VendorRequest = request.env['vendor.request'].sudo()
        
        # Domaine de recherche
        domain = [('partner_id', '=', partner.id)]
        
        # Tri par défaut
        if not sortby:
            sortby = 'date'
        sort_order = 'create_date desc'
        
        # Comptage pour la pagination
        request_count = VendorRequest.search_count(domain)
        
        # Pager
        pager = portal_pager(
            url="/my/vendor/requests",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=request_count,
            page=page,
            step=self._items_per_page
        )
        
        # Récupérer les demandes avec pagination
        vendor_requests = VendorRequest.search(
            domain,
            order=sort_order,
            limit=self._items_per_page,
            offset=pager['offset']
        )
        
        values.update({
            'page_name': 'vendor_requests',
            'pager': pager,
            'vendor_requests': vendor_requests,
            'default_url': '/my/vendor/requests',
        })
        return request.render("st_laurent_portal_vendor.portal_vendor_requests", values)
    
    @http.route(['/my/vendor/request/<int:request_id>'], type='http', auth="user", website=True)
    def vendor_request_detail(self, request_id, access_token=None, **kw):
        """
        Affiche le détail d'une demande de vendeur
        """
        try:
            # Utiliser la méthode standard de CustomerPortal pour vérifier l'accès
            vendor_request_sudo = self._document_check_access('vendor.request', request_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my/vendor/requests')
        
        # Préparer les valeurs pour le template
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'vendor_request_detail',
            'vendor_request': vendor_request_sudo,
            'default_url': f'/my/vendor/request/{request_id}',
        })
        
        # Ajouter les valeurs pour la navigation entre demandes
        history = request.session.get('my_vendor_requests_history', [()])
        values.update(get_records_pager(history, vendor_request_sudo))
        
        return request.render("st_laurent_portal_vendor.portal_vendor_request_detail", values)
        
    @http.route(['/my/vendor/request/<int:request_id>/edit'], type='http', auth="user", website=True)
    def vendor_request_edit(self, request_id, access_token=None, **kw):
        """
        Affiche le formulaire d'édition d'une demande de vendeur
        """
        try:
            # Utiliser la méthode standard de CustomerPortal pour vérifier l'accès
            vendor_request_sudo = self._document_check_access('vendor.request', request_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my/vendor/requests')
            
        # Vérifier que la demande est en état 'pending' (en attente)
        if hasattr(vendor_request_sudo, 'state') and vendor_request_sudo.state != 'pending':
            return request.redirect(f'/my/vendor/request/{request_id}')
        
        # Récupérer les pays et états autorisés selon la configuration
        config_settings = request.env['res.config.settings'].sudo()
        countries = config_settings.get_allowed_countries()
        states = config_settings.get_allowed_states()
        
        # Préparer les valeurs pour le template
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'vendor_request_edit',
            'vendor_request': vendor_request_sudo,
            'countries': countries,
            'states': states,
            'error': kw.get('error'),
            'error_message': kw.get('error_message'),
        })
        
        return request.render("st_laurent_portal_vendor.portal_vendor_request_edit", values)
        
    @http.route(['/my/vendor/request/<int:request_id>/update'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def vendor_request_update(self, request_id, **kw):
        """
        Traite la mise à jour d'une demande de vendeur
        """
        try:
            # Utiliser la méthode standard de CustomerPortal pour vérifier l'accès
            vendor_request_sudo = self._document_check_access('vendor.request', request_id)
        except (AccessError, MissingError):
            return request.redirect('/my/vendor/requests')
            
        # Vérifier que la demande est en état 'pending' (en attente)
        if hasattr(vendor_request_sudo, 'state') and vendor_request_sudo.state != 'pending':
            return request.redirect(f'/my/vendor/request/{request_id}')
        
        # Valider les données du formulaire
        if not kw.get('company_name'):
            return self.vendor_request_edit(request_id, error="missing", error_message="Le nom de l'entreprise est obligatoire.")
        
        # Mettre à jour la demande
        try:
            vals = {
                'company_name': kw.get('company_name', ''),
                'company_street': kw.get('company_street', ''),
                'company_street2': kw.get('company_street2', ''),
                'company_zip': kw.get('company_zip', ''),
                'company_city': kw.get('company_city', ''),
                'company_state_id': int(kw.get('company_state_id', '0')) if kw.get('company_state_id') and str(kw.get('company_state_id')).isdigit() else False,
                'company_country_id': int(kw.get('company_country_id', '0')) if kw.get('company_country_id') and str(kw.get('company_country_id')).isdigit() else False,
                'company_email': kw.get('company_email', ''),
                'company_phone': kw.get('company_phone', ''),
                'company_website': kw.get('company_website', ''),
                'company_vat': kw.get('company_vat', ''),
                'description': kw.get('description', ''),
            }
            
            vendor_request_sudo.write(vals)
            
            # Soumettre à nouveau la demande si nécessaire
            if kw.get('submit', False) and hasattr(vendor_request_sudo, 'action_submit'):
                vendor_request_sudo.action_submit()
            
            return request.redirect(f'/my/vendor/request/{request_id}')
            
        except Exception as e:
            return self.vendor_request_edit(request_id, error="error", error_message=str(e))


class VendorProductEcommercePortal(http.Controller):
    """
    Contrôleur pour gérer les fonctionnalités e-commerce du portail vendeur
    """
    
    @http.route(['/my/vendor'], type='http', auth="user", website=True)
    def vendor_portal_home(self, **kw):
        """
        Affiche la page d'accueil de l'espace vendeur
        """
        # Vérifier que l'utilisateur est un vendeur
        partner = request.env.user.partner_id
        if not partner.is_vendor:
            return request.redirect('/my/home')
            
        # Récupérer les produits du vendeur
        vendor_products = request.env['vendor.product'].sudo().search(
            [('partner_id', '=', partner.commercial_partner_id.id)]
        )
        
        values = {
            'page_name': 'vendor_home',
            'vendor_products': vendor_products,
        }
        
        return request.render("st_laurent_portal_vendor.portal_vendor_home", values)

    @http.route(['/my/products/<model("vendor.product"):product_id>/image'], type='http', auth="user", website=True)
    def vendor_product_image_form(self, product_id=None, **kw):
        """
        Affiche le formulaire d'upload d'image pour un produit vendeur
        """
        try:
            if not product_id:
                return request.redirect('/my/products')
                
            product_sudo = product_id.sudo()
            # Vérifier que l'utilisateur a accès à ce produit
            if product_sudo.partner_id.id != request.env.user.partner_id.commercial_partner_id.id:
                return request.redirect('/my/products')
            
            values = {
                'vendor_product': product_sudo,
                'page_name': _('Upload Product Image'),
                'error': kw.get('error'),
                'success': kw.get('success'),
            }
            return request.render("st_laurent_portal_vendor.vendor_product_image_form", values)
        except AccessError:
            return request.redirect('/my/products')

    @http.route(['/my/products/update_image'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def vendor_product_update_image(self, **kw):
        """
        Traite l'upload d'image pour un produit vendeur
        """
        product_id = kw.get('product_id')
        if not product_id:
            return request.redirect('/my/products')
        
        try:
            product = request.env['vendor.product'].sudo().browse(int(product_id))
            # Vérifier que l'utilisateur a accès à ce produit
            if product.partner_id.id != request.env.user.partner_id.commercial_partner_id.id:
                return request.redirect('/my/products')
            
            # Vérifier si une image recadrée a été fournie
            cropped_image = kw.get('cropped_image')
            if cropped_image and cropped_image.startswith('data:image/'):
                # Traiter l'image recadrée (format base64 data URL)
                try:
                    # Extraire les données base64 de l'URL data
                    image_format, image_data = cropped_image.split(';base64,')
                    image_data = base64.b64decode(image_data)
                    
                    # Mettre à jour l'image du produit
                    product.write({
                        'image_1920': base64.b64encode(image_data),
                        'website_published': True,  # Publier automatiquement le produit
                        'success': _("L'image recadrée a été mise à jour avec succès.")
                    })
                    
                    # Rediriger vers la page du produit
                    return request.redirect('/my/products/%s' % product.id)
                    
                except Exception as e:
                    return self.vendor_product_image_form(
                        product_id=product, 
                        error=_("Une erreur est survenue lors du traitement de l'image recadrée: %s") % str(e)
                    )
            
            # Si pas d'image recadrée, utiliser l'image uploadée normalement
            image_data = kw.get('product_image')
            if not image_data and not cropped_image:
                return self.vendor_product_image_form(product_id=product, error=_("Aucune image n'a été fournie."))
            
            # Traiter l'image normale
            if image_data:
                try:
                    image_data = image_data.read()
                    if len(image_data) > 5 * 1024 * 1024:  # 5 MB max
                        return self.vendor_product_image_form(
                            product_id=product, 
                            error=_("L'image est trop volumineuse. La taille maximale est de 5 Mo.")
                        )
                    
                    # Mettre à jour l'image du produit
                    product.write({
                        'image_1920': base64.b64encode(image_data),
                        'website_published': True,  # Publier automatiquement le produit
                        'success': _("L'image a été mise à jour avec succès.")
                    })
                    
                    # Rediriger vers la page du produit
                    return request.redirect('/my/products/%s' % product.id)
                    
                except Exception as e:
                    return self.vendor_product_image_form(
                        product_id=product, 
                        error=_("Une erreur est survenue lors du traitement de l'image: %s") % str(e)
                    )
            
            # Si on arrive ici, c'est qu'il y a eu un problème
            return self.vendor_product_image_form(
                product_id=product, 
                error=_("Aucune image valide n'a été fournie.")
            )
                
        except (AccessError, ValidationError) as e:
            return request.redirect('/my/products')
        except Exception as e:
            return request.redirect('/my/products')
