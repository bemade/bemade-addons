# -*- coding: utf-8 -*-

from odoo import http, _, fields
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo import fields
from datetime import datetime, timedelta, time, date
from odoo.tools import format_duration
import logging
import calendar
import dateutil.utils as date_utils

_logger = logging.getLogger(__name__)

def get_employee_from_user(user):
    """Helper method to find the employee associated with the current user.
    This handles both internal users and portal users.
    """
    employee = user.employee_id
    _logger.info("Recherche d'employé pour l'utilisateur %s (ID: %s)", user.name, user.id)
    _logger.info("Méthode 1 (employee_id): %s", employee.id if employee else None)
    
    if not employee:
        # Chercher un employé directement lié à cet utilisateur
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        _logger.info("Méthode 2 (user_id): %s", employee.id if employee else None)
    
    if not employee:
        # Essayer de trouver via la relation inverse depuis res.users
        if hasattr(user, 'employee_ids') and user.employee_ids:
            employee = user.employee_ids[0]
            _logger.info("Méthode 3 (employee_ids): %s", employee.id if employee else None)
            
    # Dernière tentative: chercher dans tous les employés si l'un d'eux a le même email
    if not employee and user.email:
        employee = request.env['hr.employee'].sudo().search([('work_email', '=', user.email)], limit=1)
        _logger.info("Méthode 4 (work_email): %s", employee.id if employee else None)
        
    _logger.info("Employé final trouvé: %s (ID: %s)", employee.name if employee else None, employee.id if employee else None)
    
    _logger.info(f"Employee found for user {user.name} (ID: {user.id}): {employee.name if employee else 'None'}")
    return employee

class PlanningSlotPortal(CustomerPortal):

    @http.route(['/my/planning/slots', '/my/planning/slots/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_planning_slots(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        """Afficher la liste des créneaux de planning de l'utilisateur."""
        values = self._prepare_portal_layout_values()
        
        # Récupérer l'employé associé à l'utilisateur connecté
        employee = get_employee_from_user(request.env.user)
        
        if not employee:
            values.update({
                'planning_slots': [],
                'page_name': 'planning_slots',
                'default_url': '/my/planning/slots',
                'pager': {'page_count': 1, 'page': {'url': '/my/planning/slots'}},
                'searchbar_sortings': {},
                'sortby': 'date',
                'searchbar_filters': {},
                'filterby': 'all',
                'no_employee': True
            })
            return request.render("portal_planning.portal_my_planning_slots", values)
        
        domain = [
            ('employee_id', '=', employee.id)
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
            'draft': {'label': _('À confirmer'), 'domain': [('portal_status', '=', 'draft')]},
            'confirmed': {'label': _('Confirmés'), 'domain': [('portal_status', '=', 'confirmed')]},
            'modified': {'label': _('Modifiés'), 'domain': [('portal_status', '=', 'modified')]},
            'pending': {'label': _('En attente'), 'domain': [('portal_status', '=', 'pending_approval')]},
        }
        
        # Filtre par défaut
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
            
        # Options de tri
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'start_datetime desc'},
            'role': {'label': _('Rôle'), 'order': 'role_id'},
            'status': {'label': _('Statut'), 'order': 'portal_status'},
        }
        
        # Tri par défaut
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Pagination
        planning_slots_count = request.env['planning.slot'].sudo().search_count(domain)
        pager = portal_pager(
            url="/my/planning/slots",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=planning_slots_count,
            page=page,
            step=self._items_per_page
        )
        
        # Récupérer les créneaux de planning
        planning_slots = request.env['planning.slot'].sudo().search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )
        
        # Préparer les valeurs pour le template
        values.update({
            'date': date_begin,
            'planning_slots': planning_slots,
            'page_name': 'planning_slots',
            'pager': pager,
            'default_url': '/my/planning/slots',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'sortby': sortby,
            'filterby': filterby,
            'format_duration': format_duration,
        })
        
        return request.render("portal_planning.portal_my_planning_slots", values)
    
    @http.route(['/my/planning/slot/create'], type='http', auth="user", website=True)
    def portal_planning_slot_create(self, date=None, **kw):
        """Page de création d'un créneau de planning"""
        values = self._prepare_portal_layout_values()
        employee = get_employee_from_user(request.env.user)
        
        if not employee:
            values.update({
                'page_name': 'planning_slot_create',
                'no_employee': True
            })
            return request.render("portal_planning.portal_my_planning_slots", values)
        
        # Préparer les valeurs par défaut
        default_values = {}
        if date:
            try:
                selected_date = datetime.strptime(date, '%Y-%m-%d').date()
                # Heures par défaut (8h à 17h)
                default_start = datetime.combine(selected_date, time(8, 0))
                default_end = datetime.combine(selected_date, time(17, 0))
                default_values.update({
                    'start_datetime': default_start,
                    'end_datetime': default_end,
                })
            except ValueError:
                pass
        
        # Récupérer les rôles disponibles
        roles = request.env['planning.role'].sudo().search([])
        
        values.update({
            'page_name': 'planning_slot_create',
            'employee': employee,
            'roles': roles,
            'default_values': default_values,
        })
        
        return request.render("portal_planning.portal_planning_slot_create", values)
    
    @http.route(['/my/planning/slot/submit'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_planning_slot_submit(self, **kw):
        """Traiter la soumission du formulaire de création de créneau"""
        # Récupérer directement l'employé de l'utilisateur courant
        employee = get_employee_from_user(request.env.user)
        
        # Vérifier que l'employé existe
        if not employee:
            _logger.warning("Aucun employé trouvé pour l'utilisateur %s (ID: %s)", 
                          request.env.user.name, request.env.user.id)
            return request.redirect('/my/planning/slots')
            
        employee_id = employee.id
        _logger.info("Utilisation de l'employé %s (ID: %s) pour la création du créneau", 
                    employee.name, employee_id)
        
        # Convertir les dates
        try:
            start_datetime = datetime.strptime(kw.get('start_datetime'), '%Y-%m-%dT%H:%M')
            end_datetime = datetime.strptime(kw.get('end_datetime'), '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError):
            return request.redirect('/my/planning/slots')
        
        # Récupérer la ressource associée à l'employé
        resource = request.env['resource.resource'].sudo().search([('employee_id', '=', employee_id)], limit=1)
        if not resource:
            _logger.warning("Aucune ressource trouvée pour l'employé %s (ID: %s)", employee.name, employee_id)
            return request.redirect('/my/planning/slots')
            
        _logger.info("Ressource trouvée pour l'employé %s (ID: %s): %s (ID: %s)", 
                    employee.name, employee_id, resource.name, resource.id)
        
        # Créer le créneau de planning avec resource_id au lieu de employee_id
        vals = {
            'resource_id': resource.id,  # Utiliser resource_id au lieu de employee_id
            'start_datetime': start_datetime,
            'end_datetime': end_datetime,
            'allocated_hours': (end_datetime - start_datetime).total_seconds() / 3600,
            'name': kw.get('name', ''),
            # Champs spécifiques à la création via le portail
            'portal_created': True,
            'portal_creation_date': fields.Datetime.now(),
            'portal_creation_user_id': request.env.user.id,
            'portal_creation_approved': 'pending',
        }
        
        # Débogage des valeurs avant création
        _logger.info("Valeurs pour la création du créneau: %s", vals)
        
        # Ajouter le rôle si spécifié
        role_id = kw.get('role_id')
        if role_id and role_id.isdigit() and int(role_id) > 0:
            vals['role_id'] = int(role_id)
        
        # Créer le créneau
        try:
            slot = request.env['planning.slot'].sudo().create(vals)
            _logger.info("Créneau de planning créé avec succès: ID=%s, start=%s, end=%s, employee_id=%s", 
                         slot.id, slot.start_datetime, slot.end_datetime, slot.employee_id.id)
            
            # Vérifier si le créneau est bien en base de données
            created_slot = request.env['planning.slot'].sudo().browse(slot.id)
            if created_slot.exists():
                _logger.info("Créneau %s existe en base de données avec employee_id=%s", 
                             created_slot.id, created_slot.employee_id.id)
            else:
                _logger.warning("Créneau %s n'existe pas en base de données après création", slot.id)
                
            # Vérifier si le créneau est visible dans une recherche directe
            domain = [
                ('id', '=', slot.id)
            ]
            found_slots = request.env['planning.slot'].sudo().search(domain)
            _logger.info("Recherche directe du créneau %s: trouvé %s créneaux", slot.id, len(found_slots))
        except Exception as e:
            _logger.error("Erreur lors de la création du créneau de planning: %s", str(e))
            return request.redirect('/my/planning/slots')
        
        # Rediriger vers la vue hebdomadaire
        return request.redirect('/my/planning/week?date_start=%s' % start_datetime.date().strftime('%Y-%m-%d'))
    
    @http.route(['/my/planning/slot/<int:slot_id>'], type='http', auth="user", website=True)
    def portal_planning_slot_detail(self, slot_id, **kw):
        """Afficher le détail d'un créneau de planning."""
        try:
            slot_sudo = request.env['planning.slot'].sudo().browse(slot_id)
            employee = get_employee_from_user(request.env.user)
            
            if not slot_sudo.exists() or not employee or slot_sudo.employee_id.id != employee.id:
                _logger.warning(f"Access denied to slot {slot_id} for user {request.env.user.id}. Employee: {employee.id if employee else 'None'}, Slot employee: {slot_sudo.employee_id.id if slot_sudo.exists() else 'None'}")
                return request.redirect('/my/planning/slots')
        except (AccessError, MissingError) as e:
            _logger.error(f"Error accessing slot {slot_id}: {str(e)}")
            return request.redirect('/my/planning/slots')
            
        values = self._prepare_portal_layout_values()
        values.update({
            'slot': slot_sudo,
            'page_name': 'planning_slot_detail',
            'format_duration': format_duration,
        })
        
        return request.render("portal_planning.portal_planning_slot", values)
    
    @http.route(['/my/planning/slot/<int:slot_id>/confirm'], type='http', auth="user", website=True)
    def portal_planning_slot_confirm(self, slot_id, **kw):
        """Confirmer un créneau de planning."""
        try:
            slot_sudo = request.env['planning.slot'].sudo().browse(slot_id)
            employee = get_employee_from_user(request.env.user)
            
            if not slot_sudo.exists() or not employee or slot_sudo.employee_id.id != employee.id:
                _logger.warning(f"Access denied to confirm slot {slot_id} for user {request.env.user.id}")
                return request.redirect('/my/planning/slots')
                
            # Vérifier si le créneau peut être confirmé
            if not slot_sudo.portal_confirmed:
                slot_sudo.action_confirm_portal()
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning/slots')
        except UserError as e:
            return request.render('portal_planning.portal_planning_error', {
                'error': str(e),
                'back_url': '/my/planning/slot/%s' % slot_id,
            })
            
        return request.redirect('/my/planning/slot/%s' % slot_id)
    
    @http.route(['/my/planning/slot/<int:slot_id>/modify'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    def portal_planning_slot_modify(self, slot_id, **kw):
        """Modifier un créneau de planning."""
        try:
            slot_sudo = request.env['planning.slot'].sudo().browse(slot_id)
            employee = get_employee_from_user(request.env.user)
            
            if not slot_sudo.exists() or not employee or slot_sudo.employee_id.id != employee.id:
                _logger.warning(f"Access denied to modify slot {slot_id} for user {request.env.user.id}")
                return request.redirect('/my/planning/slots')
                
            # Vérifier si le créneau peut être modifié
            if not slot_sudo.portal_can_modify:
                return request.redirect('/my/planning/slot/%s' % slot_id)
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning/slots')
            
        if request.httprequest.method == 'POST':
            # Validation des données du formulaire
            start_datetime = kw.get('start_datetime')
            end_datetime = kw.get('end_datetime')
            role_id = kw.get('role_id')
            notes = kw.get('notes')
            
            if not start_datetime or not end_datetime:
                return request.render('portal_planning.portal_planning_slot_modify', {
                    'error': _('Veuillez remplir tous les champs obligatoires.'),
                    'slot': slot_sudo,
                    'roles': request.env['planning.role'].sudo().search([]),
                })
            
            # Conversion des dates
            try:
                start_dt = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M')
                end_dt = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M')
            except ValueError:
                return request.render('portal_planning.portal_planning_slot_modify', {
                    'error': _('Format de date invalide.'),
                    'slot': slot_sudo,
                    'roles': request.env['planning.role'].sudo().search([]),
                })
            
            # Vérification que la date de fin est après la date de début
            if end_dt <= start_dt:
                return request.render('portal_planning.portal_planning_slot_modify', {
                    'error': _('La date de fin doit être postérieure à la date de début.'),
                    'slot': slot_sudo,
                    'roles': request.env['planning.role'].sudo().search([]),
                })
            
            # Préparation des valeurs pour la modification
            vals = {
                'start_datetime': start_dt,
                'end_datetime': end_dt,
                'portal_modification_notes': notes,
            }
            
            if role_id and role_id != '':
                vals['role_id'] = int(role_id)
            
            try:
                # Appliquer la modification
                slot_sudo.action_modify_portal(vals)
                return request.redirect('/my/planning/slot/%s' % slot_id)
            except UserError as e:
                return request.render('portal_planning.portal_planning_slot_modify', {
                    'error': str(e),
                    'slot': slot_sudo,
                    'roles': request.env['planning.role'].sudo().search([]),
                })
        
        # Affichage du formulaire de modification
        values = self._prepare_portal_layout_values()
        values.update({
            'slot': slot_sudo,
            'roles': request.env['planning.role'].sudo().search([]),
            'page_name': 'planning_slot_modify',
        })
        
        return request.render("portal_planning.portal_planning_slot_modify", values)
    
    @http.route(['/my/planning/slot/<int:slot_id>/exchange'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    def portal_planning_slot_exchange(self, slot_id, **kw):
        """Créer une demande d'échange pour un créneau de planning."""
        try:
            slot_sudo = request.env['planning.slot'].sudo().browse(slot_id)
            employee = get_employee_from_user(request.env.user)
            
            if not slot_sudo.exists() or not employee or slot_sudo.employee_id.id != employee.id:
                _logger.warning(f"Access denied to exchange slot {slot_id} for user {request.env.user.id}")
                return request.redirect('/my/planning/slots')
                
        except (AccessError, MissingError):
            return request.redirect('/my/planning/slots')
            
        if request.httprequest.method == 'POST':
            # Validation des données du formulaire
            is_open_request = kw.get('is_open_request') == 'on'
            target_slot_id = kw.get('target_slot_id')
            preferred_start = kw.get('preferred_start')
            preferred_end = kw.get('preferred_end')
            notes = kw.get('notes')
            
            # Vérification des champs requis selon le type de demande
            if is_open_request:
                if not preferred_start or not preferred_end:
                    return request.render('portal_planning.portal_planning_slot_exchange', {
                        'error': _('Veuillez spécifier les dates préférées pour votre demande ouverte.'),
                        'slot': slot_sudo,
                        'available_slots': request.env['planning.slot'].sudo().search([
                            ('employee_id.user_id', '!=', request.env.user.id),
                            ('start_datetime', '>=', datetime.now())
                        ]),
                    })
                    
                # Conversion des dates
                try:
                    start_dt = datetime.strptime(preferred_start, '%Y-%m-%dT%H:%M')
                    end_dt = datetime.strptime(preferred_end, '%Y-%m-%dT%H:%M')
                except ValueError:
                    return request.render('portal_planning.portal_planning_slot_exchange', {
                        'error': _('Format de date invalide.'),
                        'slot': slot_sudo,
                        'available_slots': request.env['planning.slot'].sudo().search([
                            ('employee_id.user_id', '!=', request.env.user.id),
                            ('start_datetime', '>=', datetime.now())
                        ]),
                    })
                
                # Vérification que la date de fin est après la date de début
                if end_dt <= start_dt:
                    return request.render('portal_planning.portal_planning_slot_exchange', {
                        'error': _('La date de fin doit être postérieure à la date de début.'),
                        'slot': slot_sudo,
                        'available_slots': request.env['planning.slot'].sudo().search([
                            ('employee_id.user_id', '!=', request.env.user.id),
                            ('start_datetime', '>=', datetime.now())
                        ]),
                    })
            else:
                if not target_slot_id:
                    return request.render('portal_planning.portal_planning_slot_exchange', {
                        'error': _('Veuillez sélectionner un créneau à échanger.'),
                        'slot': slot_sudo,
                        'available_slots': request.env['planning.slot'].sudo().search([
                            ('employee_id.user_id', '!=', request.env.user.id),
                            ('start_datetime', '>=', datetime.now())
                        ]),
                    })
            
            # Préparation des valeurs pour la demande d'échange
            vals = {
                'source_slot_id': slot_id,
                'is_open_request': is_open_request,
                'notes': notes,
            }
            
            if is_open_request:
                # Récupérer les dates préférées depuis le formulaire
                preferred_start = request.httprequest.form.get('preferred_start')
                preferred_end = request.httprequest.form.get('preferred_end')
                vals.update({
                    'preferred_start': preferred_start,
                    'preferred_end': preferred_end,
                })
            else:
                # S'assurer que target_slot_id est un entier valide
                if target_slot_id:
                    vals['target_slot_id'] = int(target_slot_id)
            
            try:
                # Créer la demande d'échange
                exchange = request.env['portal.planning.exchange'].sudo().create(vals)
                # Soumettre la demande
                exchange.action_submit()
                return request.redirect('/my/planning/exchanges')
            except UserError as e:
                return request.render('portal_planning.portal_planning_slot_exchange', {
                    'error': str(e),
                    'slot': slot_sudo,
                    'available_slots': request.env['planning.slot'].sudo().search([
                        ('employee_id.user_id', '!=', request.env.user.id),
                        ('start_datetime', '>=', datetime.now())
                    ]),
                })
        
        # Affichage du formulaire d'échange
        values = self._prepare_portal_layout_values()
        values.update({
            'slot': slot_sudo,
            'available_slots': request.env['planning.slot'].sudo().search([
                ('employee_id.user_id', '!=', request.env.user.id),
                ('start_datetime', '>=', datetime.now())
            ]),
            'page_name': 'planning_slot_exchange',
        })
        
        return request.render("portal_planning.portal_planning_slot_exchange", values)
    
    @http.route(['/my/planning/week'], type='http', auth="user", website=True)
    def portal_my_planning_week(self, date_start=None, **kw):
        """Afficher la vue hebdomadaire du planning."""
        values = self._prepare_portal_layout_values()
        
        # Récupérer l'employé associé à l'utilisateur connecté
        employee = get_employee_from_user(request.env.user)
        
        if not employee:
            values.update({
                'planning_slots': [],
                'no_employee': True,
                'page_name': 'planning_week',
                'default_url': '/my/planning/week',
            })
            return request.render("portal_planning.portal_my_planning_slots", values)
        
        # Déterminer la date de début de semaine (lundi)
        today = fields.Date.today()
        start_date = today
        if date_start:
            try:
                start_date = fields.Date.from_string(date_start)
            except ValueError:
                start_date = today
        
        # S'assurer que start_date n'est pas None
        if not start_date:
            start_date = today
            
        # Si pas de date spécifiée, prendre le lundi de la semaine courante
        weekday = start_date.weekday()
        start_date = start_date - timedelta(days=weekday)
        
        # Calculer la date de fin de semaine (dimanche)
        end_date = start_date + timedelta(days=6)
        
        # Convertir en datetime pour la recherche
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Récupérer les créneaux de planning pour la semaine
        domain = [
            ('employee_id', '=', employee.id),
            '|', '|',
            '&', ('start_datetime', '>=', start_datetime), ('start_datetime', '<=', end_datetime),
            '&', ('end_datetime', '>=', start_datetime), ('end_datetime', '<=', end_datetime),
            '&', ('start_datetime', '<=', start_datetime), ('end_datetime', '>=', end_datetime),
        ]
        
        # Ajouter des logs pour débogage
        _logger.info("Recherche de créneaux pour la semaine du %s au %s", start_date, end_date)
        _logger.info("Domaine de recherche: %s", domain)
        
        slots = request.env['planning.slot'].sudo().search(domain, order='start_datetime')
        
        # Ajouter des logs pour débogage
        _logger.info("Créneaux trouvés pour la semaine: %s", slots.ids)
        
        # Organiser les créneaux par jour
        days = []
        current_date = start_date
        while current_date <= end_date:
            day_slots = slots.filtered(lambda s: s.start_datetime.date() <= current_date and s.end_datetime.date() >= current_date)
            days.append({
                'date': current_date,
                'name': current_date.strftime('%A'),
                'day_slots': day_slots,
                'is_today': current_date == today,
            })
            current_date += timedelta(days=1)
        
        # Préparer les valeurs pour le template
        values.update({
            'employee': employee,
            'days': days,
            'start_date': start_date,
            'end_date': end_date,
            'prev_week': (start_date - timedelta(days=7)).strftime('%Y-%m-%d'),
            'next_week': (start_date + timedelta(days=7)).strftime('%Y-%m-%d'),
            'today': today.strftime('%Y-%m-%d'),
            'page_name': 'planning_week',
            'default_url': '/my/planning/week',
            'format_duration': format_duration,
        })
        
        return request.render("portal_planning.portal_my_planning_slots", values)
    
    @http.route(['/my/planning/day'], type='http', auth="user", website=True)
    def portal_my_planning_day(self, date=None, **kw):
        """Afficher la vue quotidienne du planning."""
        values = self._prepare_portal_layout_values()
        
        # Récupérer l'employé associé à l'utilisateur connecté
        employee = get_employee_from_user(request.env.user)
        
        if not employee:
            values.update({
                'planning_slots': [],
                'no_employee': True,
                'page_name': 'planning_day',
                'default_url': '/my/planning/day',
            })
            return request.render("portal_planning.portal_my_planning_slots", values)
        
        # Déterminer la date à afficher
        today = fields.Date.today()
        selected_date = today
        if date:
            try:
                selected_date = fields.Date.from_string(date)
            except ValueError:
                selected_date = today
        
        # Convertir en datetime pour la recherche
        start_datetime = datetime.combine(selected_date, datetime.min.time())
        end_datetime = datetime.combine(selected_date, datetime.max.time())
        
        # Récupérer les créneaux de planning pour le jour
        domain = [
            ('employee_id', '=', employee.id),
            '|',
            '&', ('start_datetime', '>=', start_datetime), ('start_datetime', '<=', end_datetime),
            '&', ('end_datetime', '>=', start_datetime), ('end_datetime', '<=', end_datetime),
        ]
        
        slots = request.env['planning.slot'].sudo().search(domain, order='start_datetime')
        
        # Préparer les valeurs pour le template
        values.update({
            'employee': employee,
            'planning_slots': slots,  # Utiliser la même clé que dans la vue standard
            'selected_date': selected_date,
            'prev_day': (selected_date - timedelta(days=1)).strftime('%Y-%m-%d'),
            'next_day': (selected_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            'today': today.strftime('%Y-%m-%d'),
            'is_today': selected_date == today,
            'page_name': 'planning_day',
            'default_url': '/my/planning/day',
            'format_duration': format_duration,
            'view_mode': 'day',  # Indiquer le mode d'affichage
        })
        
        return request.render("portal_planning.portal_my_planning_slots", values)
