# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError, UserError
from datetime import datetime

class PlanningExchangePortal(CustomerPortal):

    @http.route(['/my/planning/exchanges', '/my/planning/exchanges/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_planning_exchanges(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        """Afficher la liste des demandes d'échange de l'utilisateur."""
        values = self._prepare_portal_layout_values()
        
        domain = [
            '|',
            ('source_user_id', '=', request.env.user.id),
            ('target_user_id', '=', request.env.user.id)
        ]
        
        # Filtrer par date si spécifié
        if date_begin and date_end:
            domain += [
                ('date', '>=', date_begin),
                ('date', '<=', date_end)
            ]
        
        # Filtrer par état
        searchbar_filters = {
            'all': {'label': _('Tous'), 'domain': []},
            'draft': {'label': _('Brouillons'), 'domain': [('state', '=', 'draft')]},
            'pending': {'label': _('En attente'), 'domain': [('state', '=', 'pending')]},
            'accepted': {'label': _('Acceptés'), 'domain': [('state', '=', 'accepted')]},
            'approved': {'label': _('Approuvés'), 'domain': [('state', '=', 'approved')]},
            'rejected': {'label': _('Refusés'), 'domain': [('state', '=', 'rejected')]},
            'cancelled': {'label': _('Annulés'), 'domain': [('state', '=', 'cancelled')]},
        }
        
        # Filtre par défaut
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
            
        # Options de tri
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'date desc'},
            'state': {'label': _('État'), 'order': 'state'},
        }
        
        # Tri par défaut
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Pagination
        exchange_count = request.env['portal.planning.exchange'].sudo().search_count(domain)
        pager = portal_pager(
            url="/my/planning/exchanges",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=exchange_count,
            page=page,
            step=self._items_per_page
        )
        
        # Récupérer les demandes d'échange
        exchanges = request.env['portal.planning.exchange'].sudo().search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )
        
        # Préparer les valeurs pour le template
        values.update({
            'date': date_begin,
            'exchanges': exchanges,
            'page_name': 'planning_exchanges',
            'pager': pager,
            'default_url': '/my/planning/exchanges',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'sortby': sortby,
            'filterby': filterby,
        })
        
        return request.render("portal_planning.portal_my_planning_exchanges", values)
    
    @http.route(['/my/planning/exchange/<int:exchange_id>'], type='http', auth="user", website=True)
    def portal_planning_exchange_detail(self, exchange_id):
        """Afficher le détail d'une demande d'échange."""
        try:
            exchange_sudo = request.env['portal.planning.exchange'].sudo().browse(exchange_id)
            if not exchange_sudo.exists() or (exchange_sudo.source_user_id.id != request.env.user.id and exchange_sudo.target_user_id.id != request.env.user.id):
                return request.redirect('/my/planning/exchanges')
        except (AccessError, MissingError):
            return request.redirect('/my/planning/exchanges')
            
        values = self._prepare_portal_layout_values()
        values.update({
            'exchange': exchange_sudo,
            'page_name': 'planning_exchange_detail',
        })
        
        return request.render("portal_planning.portal_planning_exchange_detail", values)
    
    @http.route(['/my/planning/exchange/<int:exchange_id>/accept'], type='http', auth="user", website=True)
    def portal_planning_exchange_accept(self, exchange_id):
        """Accepter une demande d'échange."""
        try:
            exchange_sudo = request.env['portal.planning.exchange'].sudo().browse(exchange_id)
            if not exchange_sudo.exists() or exchange_sudo.target_user_id.id != request.env.user.id:
                return request.redirect('/my/planning/exchanges')
                
            if exchange_sudo.can_accept:
                exchange_sudo.action_accept()
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning/exchanges')
        except UserError as e:
            return request.render('portal_planning.portal_planning_error', {
                'error': str(e),
                'back_url': '/my/planning/exchange/%s' % exchange_id,
            })
            
        return request.redirect('/my/planning/exchange/%s' % exchange_id)
    
    @http.route(['/my/planning/exchange/<int:exchange_id>/cancel'], type='http', auth="user", website=True)
    def portal_planning_exchange_cancel(self, exchange_id):
        """Annuler une demande d'échange."""
        try:
            exchange_sudo = request.env['portal.planning.exchange'].sudo().browse(exchange_id)
            if not exchange_sudo.exists() or exchange_sudo.source_user_id.id != request.env.user.id:
                return request.redirect('/my/planning/exchanges')
                
            if exchange_sudo.can_cancel:
                exchange_sudo.action_cancel()
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning/exchanges')
        except UserError as e:
            return request.render('portal_planning.portal_planning_error', {
                'error': str(e),
                'back_url': '/my/planning/exchange/%s' % exchange_id,
            })
            
        return request.redirect('/my/planning/exchange/%s' % exchange_id)
