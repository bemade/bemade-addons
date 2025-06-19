# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request, Response
from odoo.exceptions import AccessError, MissingError, UserError
import json
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class PlanningPortalAPI(http.Controller):
    """Contrôleur pour l'API JSON du planning dans le portail."""
    
    def _get_employee_from_user(self):
        """Récupère l'employé correspondant à l'utilisateur connecté."""
        return request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
    
    def _check_slot_access(self, slot_id):
        """Vérifie que l'utilisateur a accès au créneau de planning."""
        employee = self._get_employee_from_user()
        if not employee:
            return False, "Aucun employé associé à cet utilisateur"
            
        slot = request.env['planning.slot'].sudo().browse(slot_id)
        if not slot.exists():
            return False, "Créneau de planning introuvable"
            
        if slot.employee_id.id != employee.id:
            return False, "Vous n'avez pas accès à ce créneau de planning"
            
        return True, slot
    
    @http.route(['/planning/api/slot/update'], type='json', auth="user", methods=['POST'], website=True)
    def update_slot(self, **kw):
        """Endpoint pour mettre à jour un créneau de planning."""
        slot_id = kw.get('slot_id')
        if not slot_id:
            return {'success': False, 'error': "ID du créneau manquant"}
            
        access, result = self._check_slot_access(slot_id)
        if not access:
            return {'success': False, 'error': result}
            
        slot = result
        
        # Récupérer les données de mise à jour
        start_datetime = kw.get('start_datetime')
        end_datetime = kw.get('end_datetime')
        role_id = kw.get('role_id')
        notes = kw.get('notes')
        
        # Valider les données
        if start_datetime and end_datetime:
            try:
                start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_datetime.replace('Z', '+00:00'))
                
                if start_dt >= end_dt:
                    return {'success': False, 'error': "La date de début doit être antérieure à la date de fin"}
            except ValueError:
                return {'success': False, 'error': "Format de date invalide"}
        
        # Préparer les valeurs pour la modification
        vals = {}
        if start_datetime:
            vals['start_datetime'] = start_datetime
        if end_datetime:
            vals['end_datetime'] = end_datetime
        if role_id:
            vals['role_id'] = int(role_id)
        
        try:
            # Créer une modification via le portail
            modification_vals = {
                'slot_id': slot.id,
                'user_id': request.env.user.id,
                'start_datetime': start_datetime if start_datetime else slot.start_datetime,
                'end_datetime': end_datetime if end_datetime else slot.end_datetime,
                'role_id': int(role_id) if role_id else slot.role_id.id if slot.role_id else False,
                'notes': notes,
                'state': 'draft'
            }
            
            modification = request.env['portal.planning.modification'].sudo().create(modification_vals)
            # Soumettre la modification
            if hasattr(modification, 'action_submit'):
                modification.action_submit()
            
            return {
                'success': True,
                'message': "Demande de modification soumise avec succès",
                'modification_id': modification.id,
                'state': modification.state
            }
            
        except Exception as e:
            _logger.error("Erreur lors de la mise à jour du créneau: %s", str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route(['/planning/api/slot/confirm'], type='json', auth="user", methods=['POST'], website=True)
    def confirm_slot(self, **kw):
        """Endpoint pour confirmer un créneau de planning."""
        slot_id = kw.get('slot_id')
        if not slot_id:
            return {'success': False, 'error': "ID du créneau manquant"}
            
        access, result = self._check_slot_access(slot_id)
        if not access:
            return {'success': False, 'error': result}
            
        slot = result
        
        try:
            # Confirmer le créneau
            if hasattr(slot, 'action_confirm_portal'):
                slot.action_confirm_portal()
            
            return {
                'success': True,
                'message': "Créneau confirmé avec succès",
                'portal_status': slot.portal_status if hasattr(slot, 'portal_status') else 'confirmed'
            }
            
        except Exception as e:
            _logger.error("Erreur lors de la confirmation du créneau: %s", str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route(['/planning/api/slot/exchange/request'], type='json', auth="user", methods=['POST'], website=True)
    def request_exchange(self, **kw):
        """Endpoint pour demander un échange de créneau."""
        source_slot_id = kw.get('source_slot_id')
        target_slot_id = kw.get('target_slot_id')
        is_open_request = kw.get('is_open_request', False)
        preferred_start = kw.get('preferred_start')
        preferred_end = kw.get('preferred_end')
        notes = kw.get('notes')
        
        if not source_slot_id:
            return {'success': False, 'error': "ID du créneau source manquant"}
            
        access, result = self._check_slot_access(source_slot_id)
        if not access:
            return {'success': False, 'error': result}
            
        source_slot = result
        
        # Valider les données pour une demande ouverte
        if is_open_request and preferred_start and preferred_end:
            try:
                start_dt = datetime.fromisoformat(preferred_start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(preferred_end.replace('Z', '+00:00'))
                
                if start_dt >= end_dt:
                    return {'success': False, 'error': "La date de début doit être antérieure à la date de fin"}
            except ValueError:
                return {'success': False, 'error': "Format de date invalide"}
        
        # Valider le créneau cible pour une demande spécifique
        if not is_open_request and target_slot_id:
            target_slot = request.env['planning.slot'].sudo().browse(target_slot_id)
            if not target_slot.exists():
                return {'success': False, 'error': "Créneau cible introuvable"}
                
            # Vérifier que le créneau cible n'appartient pas à l'utilisateur
            if target_slot.employee_id.user_id.id == request.env.user.id:
                return {'success': False, 'error': "Vous ne pouvez pas échanger avec votre propre créneau"}
        
        try:
            # Préparer les valeurs pour la demande d'échange
            slot_name = source_slot.name if hasattr(source_slot, 'name') and source_slot.name else 'créneau'
            slot_date = source_slot.start_datetime.strftime('%d/%m/%Y') if hasattr(source_slot, 'start_datetime') else ''
            
            exchange_vals = {
                'name': f"Demande d'échange pour {slot_name} du {slot_date}",
                'source_slot_id': source_slot.id,
                'source_user_id': request.env.user.id,
                'notes': notes,
                'state': 'draft',
                'is_open_request': is_open_request
            }
            
            if is_open_request:
                if preferred_start:
                    exchange_vals['preferred_start'] = preferred_start
                if preferred_end:
                    exchange_vals['preferred_end'] = preferred_end
            else:
                if target_slot_id:
                    exchange_vals['target_slot_id'] = target_slot_id
                    exchange_vals['target_user_id'] = target_slot.employee_id.user_id.id
            
            # Créer la demande d'échange
            exchange = request.env['portal.planning.exchange'].sudo().create(exchange_vals)
            
            # Soumettre la demande
            exchange.action_submit()
            
            return {
                'success': True,
                'message': "Demande d'échange soumise avec succès",
                'exchange_id': exchange.id,
                'state': exchange.state
            }
            
        except Exception as e:
            _logger.error("Erreur lors de la création de la demande d'échange: %s", str(e))
            return {'success': False, 'error': str(e)}
            
    @http.route(['/planning/api/slots'], type='json', auth="user", methods=['POST'], website=True)
    def get_slots(self, **kw):
        """Endpoint pour récupérer les créneaux de planning pour le calendrier."""
        start_date = kw.get('start_date')
        end_date = kw.get('end_date')
        
        if not start_date or not end_date:
            return {'success': False, 'error': "Dates de début et de fin requises"}
            
        try:
            # Convertir les dates en objets datetime
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_dt = end_dt.replace(hour=23, minute=59, second=59)  # Inclure toute la journée de fin
            
            # Récupérer l'employé correspondant à l'utilisateur connecté
            employee = self._get_employee_from_user()
            if not employee:
                return {'success': False, 'error': "Aucun employé associé à cet utilisateur"}
                
            # Récupérer les créneaux de planning pour l'employé dans la période spécifiée
            domain = [
                ('employee_id', '=', employee.id),
                '|',
                '&', ('start_datetime', '>=', start_dt), ('start_datetime', '<=', end_dt),
                '&', ('end_datetime', '>=', start_dt), ('end_datetime', '<=', end_dt)
            ]
            
            slots = request.env['planning.slot'].sudo().search_read(domain, [
                'id', 'name', 'start_datetime', 'end_datetime', 'employee_id', 'role_id',
                'allocated_hours', 'portal_status', 'portal_confirmed', 'portal_modified',
                'portal_can_modify'
            ])
            
            return {
                'success': True,
                'slots': slots
            }
            
        except ValueError as e:
            return {'success': False, 'error': "Format de date invalide"}
        except Exception as e:
            _logger.error("Erreur lors de la récupération des créneaux: %s", str(e))
            return {'success': False, 'error': str(e)}
