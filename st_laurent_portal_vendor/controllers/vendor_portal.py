# -*- coding: utf-8 -*-

import base64
import werkzeug

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError


class VendorPortalController(http.Controller):
    """
    Contrôleur pour gérer les fonctionnalités du portail vendeur
    """

    @http.route(['/my/vendor'], type='http', auth="user", website=True)
    def vendor_portal_home(self, **kw):
        """
        Page d'accueil du portail vendeur
        """
        # Vérifier si l'utilisateur est un vendeur
        if not request.env.user.is_vendor:
            return request.redirect('/my')
            
        # Récupérer les produits du vendeur
        vendor_products = request.env['vendor.product'].sudo().search([
            ('partner_id', '=', request.env.user.partner_id.commercial_partner_id.id)
        ])
        
        values = {
            'page_name': _('Portail Vendeur'),
            'vendor_products': vendor_products,
        }
        return request.render("st_laurent_portal_vendor.vendor_portal_home", values)

    @http.route(['/my/vendor/requests'], type='http', auth="user", website=True)
    def vendor_requests(self, **kw):
        """
        Liste des demandes de vendeur de l'utilisateur
        """
        # Récupérer les demandes de l'utilisateur
        requests = request.env['vendor.request'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ])
        
        values = {
            'page_name': _('Mes demandes de vendeur'),
            'requests': requests,
        }
        return request.render("st_laurent_portal_vendor.portal_my_vendor_requests", values)

    @http.route(['/my/vendor/request/new'], type='http', auth="user", website=True)
    def vendor_request_new(self, **kw):
        """
        Formulaire de création d'une nouvelle demande de vendeur
        """
        # Vérifier si l'utilisateur est déjà un vendeur
        if request.env.user.is_vendor:
            return request.redirect('/my')
            
        # Vérifier s'il y a déjà une demande en attente
        pending_request = request.env['vendor.request'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('state', 'in', ['pending', 'approved'])
        ], limit=1)
        
        if pending_request:
            return request.redirect('/my/vendor/request/%s' % pending_request.id)
            
        # Récupérer le brouillon existant ou en créer un nouveau
        draft_request = request.env['vendor.request'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('state', '=', 'draft')
        ], limit=1)
        
        values = {
            'page_name': _('Nouvelle demande de vendeur'),
            'vendor_request': draft_request,
            'error': kw.get('error'),
        }
        return request.render("st_laurent_portal_vendor.portal_vendor_request_form", values)

    @http.route(['/my/vendor/request/edit/<int:request_id>'], type='http', auth="user", website=True)
    def vendor_request_edit(self, request_id, **kw):
        """
        Formulaire d'édition d'une demande de vendeur existante
        """
        try:
            # Récupérer la demande
            vendor_request = request.env['vendor.request'].sudo().browse(request_id)
            
            # Vérifier que l'utilisateur a accès à cette demande
            if vendor_request.user_id.id != request.env.user.id:
                return request.redirect('/my')
                
            # Vérifier que la demande est en brouillon
            if vendor_request.state != 'draft':
                return request.redirect('/my/vendor/request/%s' % vendor_request.id)
            
            values = {
                'page_name': _('Modifier ma demande de vendeur'),
                'vendor_request': vendor_request,
                'error': kw.get('error'),
            }
            return request.render("st_laurent_portal_vendor.portal_vendor_request_form", values)
        except Exception as e:
            return request.redirect('/my')

    @http.route(['/my/vendor/request/<int:request_id>'], type='http', auth="user", website=True)
    def vendor_request_detail(self, request_id, **kw):
        """
        Vue détaillée d'une demande de vendeur
        """
        try:
            # Récupérer la demande
            vendor_request = request.env['vendor.request'].sudo().browse(request_id)
            
            # Vérifier que l'utilisateur a accès à cette demande
            if vendor_request.user_id.id != request.env.user.id:
                return request.redirect('/my')
            
            values = {
                'page_name': _('Demande de vendeur'),
                'vendor_request': vendor_request,
            }
            return request.render("st_laurent_portal_vendor.portal_vendor_request_details", values)
        except Exception as e:
            return request.redirect('/my')

    @http.route(['/my/vendor/request/submit'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def vendor_request_submit(self, **kw):
        """
        Traite la soumission d'une demande de vendeur
        """
        # Récupérer les données du formulaire
        request_id = kw.get('request_id')
        company_name = kw.get('company_name')
        description = kw.get('description')
        attachments = request.httprequest.files.getlist('attachments')
        
        if not company_name or not description:
            return request.redirect('/my/vendor/request/new?error=%s' % _("Tous les champs sont obligatoires."))
        
        try:
            VendorRequest = request.env['vendor.request'].sudo()
            
            # Créer ou mettre à jour la demande
            if request_id and request_id.isdigit():
                vendor_request = VendorRequest.browse(int(request_id))
                # Vérifier que l'utilisateur a accès à cette demande
                if vendor_request.user_id.id != request.env.user.id:
                    return request.redirect('/my')
                    
                # Mettre à jour la demande
                vendor_request.write({
                    'company_name': company_name,
                    'description': description,
                })
            else:
                # Créer une nouvelle demande
                vendor_request = VendorRequest.create({
                    'user_id': request.env.user.id,
                    'company_name': company_name,
                    'description': description,
                })
            
            # Traiter les pièces jointes
            attachment_ids = []
            for attachment in attachments:
                if attachment.filename:
                    attachment_data = {
                        'name': attachment.filename,
                        'datas': base64.b64encode(attachment.read()),
                        'res_model': 'vendor.request',
                        'res_id': vendor_request.id,
                    }
                    new_attachment = request.env['ir.attachment'].sudo().create(attachment_data)
                    attachment_ids.append(new_attachment.id)
            
            if attachment_ids:
                vendor_request.write({
                    'attachment_ids': [(4, id) for id in attachment_ids]
                })
            
            # Soumettre la demande
            vendor_request.action_submit()
            
            return request.redirect('/my/vendor/request/%s' % vendor_request.id)
        except ValidationError as e:
            return request.redirect('/my/vendor/request/new?error=%s' % e)
        except Exception as e:
            return request.redirect('/my/vendor/request/new?error=%s' % _("Une erreur est survenue lors de la soumission de votre demande."))

    @http.route(['/my/vendor/request/submit/<int:request_id>'], type='http', auth="user", website=True)
    def vendor_request_submit_direct(self, request_id, **kw):
        """
        Soumet directement une demande de vendeur existante
        """
        try:
            # Récupérer la demande
            vendor_request = request.env['vendor.request'].sudo().browse(request_id)
            
            # Vérifier que l'utilisateur a accès à cette demande
            if vendor_request.user_id.id != request.env.user.id:
                return request.redirect('/my')
                
            # Vérifier que la demande est en brouillon
            if vendor_request.state != 'draft':
                return request.redirect('/my/vendor/request/%s' % vendor_request.id)
            
            # Soumettre la demande
            vendor_request.action_submit()
            
            return request.redirect('/my/vendor/request/%s' % vendor_request.id)
        except ValidationError as e:
            return request.redirect('/my/vendor/request/%s?error=%s' % (request_id, e))
        except Exception as e:
            return request.redirect('/my/vendor/request/%s?error=%s' % (request_id, _("Une erreur est survenue lors de la soumission de votre demande.")))
