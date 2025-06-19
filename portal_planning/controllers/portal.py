from odoo import http, _, fields
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal as PortalCustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError, UserError
from datetime import datetime, timedelta
from odoo.tools import format_duration

class PlanningPortal(PortalCustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        
        if 'planning_count' in counters:
            # Compter les demandes de planning pour l'utilisateur connecté
            planning_count = request.env['portal.planning.request'].sudo().search_count([
                ('user_id', '=', request.env.user.id)
            ])
            values['planning_count'] = planning_count
            
            # Compter les créneaux de planning pour l'utilisateur connecté
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
            if employee:
                slots_count = request.env['planning.slot'].sudo().search_count([
                    ('employee_id', '=', employee.id)
                ])
                values['planning_slots_count'] = slots_count
            else:
                values['planning_slots_count'] = 0
                
            # Compter les demandes d'échange pour l'utilisateur connecté
            exchanges_count = request.env['portal.planning.exchange'].sudo().search_count([
                ('source_user_id', '=', request.env.user.id)
            ])
            values['planning_exchanges_count'] = exchanges_count
                
        return values

    @http.route(['/my/planning', '/my/planning/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_planning(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        
        domain = [
            ('user_id', '=', request.env.user.id)
        ]
        
        # Filtrer par date si spécifié
        if date_begin and date_end:
            domain += [
                ('start_datetime', '>=', date_begin),
                ('end_datetime', '<=', date_end)
            ]
        
        # Filtrer par état
        searchbar_filters = {
            'all': {'label': _('Tous'), 'domain': []},
            'draft': {'label': _('Brouillon'), 'domain': [('state', '=', 'draft')]},
            'submitted': {'label': _('Soumis'), 'domain': [('state', '=', 'submitted')]},
            'approved': {'label': _('Approuvé'), 'domain': [('state', '=', 'approved')]},
            'rejected': {'label': _('Refusé'), 'domain': [('state', '=', 'rejected')]},
            'cancelled': {'label': _('Annulé'), 'domain': [('state', '=', 'cancelled')]},
        }
        
        # Filtre par défaut
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
            
        # Options de tri
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'start_datetime desc'},
            'name': {'label': _('Titre'), 'order': 'name'},
            'state': {'label': _('État'), 'order': 'state'},
        }
        
        # Tri par défaut
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Pagination
        planning_count = request.env['portal.planning.request'].sudo().search_count(domain)
        pager = portal_pager(
            url="/my/planning",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=planning_count,
            page=page,
            step=self._items_per_page
        )
        
        # Récupérer les demandes de planning
        planning_requests = request.env['portal.planning.request'].sudo().search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )
        
        # Préparer les valeurs pour le template
        values.update({
            'date': date_begin,
            'planning_requests': planning_requests,
            'page_name': 'planning',
            'pager': pager,
            'default_url': '/my/planning',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'sortby': sortby,
            'filterby': filterby,
            'format_duration': format_duration,
        })
        
        return request.render("portal_planning.portal_my_planning", values)
        
    @http.route(['/my/planning/<int:planning_id>'], type='http', auth="user", website=True)
    def portal_my_planning_detail(self, planning_id, **kw):
        try:
            planning_sudo = request.env['portal.planning.request'].sudo().browse(planning_id)
            if not planning_sudo.exists() or planning_sudo.user_id.id != request.env.user.id:
                return request.redirect('/my/planning')
        except (AccessError, MissingError):
            return request.redirect('/my/planning')
            
        values = self._prepare_portal_layout_values()
        values.update({
            'planning': planning_sudo,
            'page_name': 'planning_detail',
            'format_duration': format_duration,
        })
        
        return request.render("portal_planning.portal_my_planning_detail", values)
        
    @http.route(['/my/planning/create'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    def portal_planning_create(self, **kw):
        """Création d'une nouvelle demande de planning."""
        if request.httprequest.method == 'POST':
            # Validation des données du formulaire
            name = kw.get('name')
            start_datetime = kw.get('start_datetime')
            end_datetime = kw.get('end_datetime')
            role_id = kw.get('role_id')
            description = kw.get('description')
            
            if not name or not start_datetime or not end_datetime:
                return request.render('portal_planning.portal_planning_create', {
                    'error': _('Veuillez remplir tous les champs obligatoires.'),
                    'roles': request.env['planning.role'].sudo().search([]),
                })
            
            # Conversion des dates
            try:
                start_dt = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M')
                end_dt = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M')
            except ValueError:
                return request.render('portal_planning.portal_planning_create', {
                    'error': _('Format de date invalide.'),
                    'roles': request.env['planning.role'].sudo().search([]),
                })
            
            # Vérification que la date de fin est après la date de début
            if end_dt <= start_dt:
                return request.render('portal_planning.portal_planning_create', {
                    'error': _('La date de fin doit être postérieure à la date de début.'),
                    'roles': request.env['planning.role'].sudo().search([]),
                })
            
            # Création de la demande de planning
            vals = {
                'name': name,
                'start_datetime': start_dt,
                'end_datetime': end_dt,
                'description': description,
                'employee_id': request.env.user.employee_id.id,
                'state': 'draft',
            }
            
            if role_id and role_id != '':
                vals['role_id'] = int(role_id)
            
            planning_request = request.env['portal.planning.request'].sudo().create(vals)
            
            return request.redirect('/my/planning/%s' % planning_request.id)
        
        # Affichage du formulaire de création
        values = self._prepare_portal_layout_values()
        values.update({
            'roles': request.env['planning.role'].sudo().search([]),
            'page_name': 'planning_create',
        })
        
        return request.render("portal_planning.portal_planning_create", values)
    
    @http.route(['/my/planning/submit/<int:planning_id>'], type='http', auth="user", website=True)
    def portal_planning_submit(self, planning_id, **kw):
        """Soumettre une demande de planning."""
        try:
            planning_sudo = request.env['portal.planning.request'].sudo().browse(planning_id)
            if not planning_sudo.exists() or planning_sudo.user_id.id != request.env.user.id:
                return request.redirect('/my/planning')
                
            if planning_sudo.can_submit:
                planning_sudo.action_submit()
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning')
            
        return request.redirect('/my/planning/%s' % planning_id)
    
    @http.route(['/my/planning/cancel/<int:planning_id>'], type='http', auth="user", website=True)
    def portal_planning_cancel(self, planning_id, **kw):
        """Annuler une demande de planning."""
        try:
            planning_sudo = request.env['portal.planning.request'].sudo().browse(planning_id)
            if not planning_sudo.exists() or planning_sudo.user_id.id != request.env.user.id:
                return request.redirect('/my/planning')
                
            if planning_sudo.can_cancel:
                planning_sudo.action_cancel()
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning')
            
        return request.redirect('/my/planning/%s' % planning_id)
    
    @http.route(['/my/planning/reset/<int:planning_id>'], type='http', auth="user", website=True)
    def portal_planning_reset(self, planning_id, **kw):
        """Remettre une demande de planning en brouillon."""
        try:
            planning_sudo = request.env['portal.planning.request'].sudo().browse(planning_id)
            if not planning_sudo.exists() or planning_sudo.user_id.id != request.env.user.id:
                return request.redirect('/my/planning')
                
            if planning_sudo.state in ['rejected', 'cancelled']:
                planning_sudo.action_reset_to_draft()
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning')
            
        return request.redirect('/my/planning/%s' % planning_id)
    
    @http.route(['/my/planning/calendar'], type='http', auth="user", website=True)
    def portal_planning_calendar(self, **kw):
        """Affichage du calendrier des créneaux de planning."""
        values = self._prepare_portal_layout_values()
        
        # Récupérer l'employé correspondant à l'utilisateur connecté
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
        
        values.update({
            'page_name': 'planning_calendar',
            'employee': employee,
        })
        
        return request.render("portal_planning.portal_planning_calendar", values)
    
    @http.route(['/my/planning/view_slot/<int:planning_id>'], type='http', auth="user", website=True)
    def portal_planning_view_slot(self, planning_id, **kw):
        """Voir le créneau de planning associé à une demande."""
        try:
            planning_sudo = request.env['portal.planning.request'].sudo().browse(planning_id)
            if not planning_sudo.exists() or planning_sudo.user_id.id != request.env.user.id:
                return request.redirect('/my/planning')
                
            if planning_sudo.planning_slot_id:
                # Préparer les valeurs pour le template
                values = self._prepare_portal_layout_values()
                values.update({
                    'planning': planning_sudo,
                    'slot': planning_sudo.planning_slot_id,
                    'page_name': 'planning_slot',
                    'format_duration': format_duration,
                })
                
                return request.render("portal_planning.portal_planning_slot", values)
            else:
                return request.redirect('/my/planning/%s' % planning_id)
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning')
        
    @http.route(['/my/planning/unassign/<int:planning_id>'], type='http', auth="user", website=True)
    def portal_planning_unassign(self, planning_id, **kw):
        try:
            planning_request = request.env['portal.planning.request'].sudo().browse(planning_id)
            if not planning_request.exists() or planning_request.user_id.id != request.env.user.id:
                return request.redirect('/my/planning')
                
            # Vérifier si le planning a un créneau associé
            if not planning_request.planning_slot_id:
                return request.redirect('/my/planning?error=no_slot_to_unassign')
                
            # Vérifier si le désassignement est autorisé (à implémenter selon les règles métier)
            # Par exemple, vérifier si la date de début est suffisamment loin dans le futur
            if planning_request.planning_slot_id.start_datetime < datetime.now() + timedelta(days=1):
                return request.redirect('/my/planning?error=unassign_deadline_passed')
                
            # Annuler la demande de planning
            planning_request.write({
                'state': 'cancelled',
            })
            
            # Libérer le créneau si nécessaire
            if planning_request.planning_slot_id:
                planning_request.planning_slot_id.write({
                    'employee_id': False,
                    'portal_status': 'draft',
                })
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning')
            
        return request.redirect('/my/planning?message=unassign_success')
        
    @http.route(['/my/planning/switch/<int:planning_id>'], type='http', auth="user", website=True)
    def portal_planning_switch(self, planning_id, **kw):
        try:
            planning_request = request.env['portal.planning.request'].sudo().browse(planning_id)
            if not planning_request.exists() or planning_request.user_id.id != request.env.user.id:
                return request.redirect('/my/planning')
                
            # Vérifier si le planning a un créneau associé
            if not planning_request.planning_slot_id:
                return request.redirect('/my/planning?error=no_slot_to_exchange')
                
            # Créer une demande d'échange
            exchange_vals = {
                'name': f"Demande d'échange pour {planning_request.name}",
                'source_slot_id': planning_request.planning_slot_id.id,
                'source_user_id': request.env.user.id,
                'notes': 'Demande d\'échange initiée depuis le portail',
                'state': 'draft',
            }
            
            exchange = request.env['portal.planning.exchange'].sudo().create(exchange_vals)
            
            # Rediriger vers la page de la demande d'échange
            return request.redirect(f'/my/planning/exchange/{exchange.id}')
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning')
            
        return request.redirect('/my/planning/exchanges?message=exchange_created')
