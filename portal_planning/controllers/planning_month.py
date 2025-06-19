# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
from datetime import datetime, timedelta, date
import calendar
import logging

from .planning_slot import get_employee_from_user
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

class PlanningMonthController(http.Controller):
    
    @http.route(['/my/planning/month'], type='http', auth="user", website=True)
    def portal_my_planning_month(self, date=None, **kw):
        """Afficher la vue mensuelle du planning."""
        portal = CustomerPortal()
        values = portal._prepare_portal_layout_values()
        
        # Récupérer l'employé associé à l'utilisateur connecté
        employee = get_employee_from_user(request.env.user)
        
        if not employee:
            return request.redirect('/my')
        
        # Obtenir la date du premier jour du mois sélectionné
        today = datetime.now().date()
        if date is None:
            selected_date = today.replace(day=1)
        elif isinstance(date, str):
            try:
                year, month = map(int, date.split('-'))
                selected_date = date(year, month, 1)
            except (ValueError, TypeError):
                selected_date = today.replace(day=1)
        else:
            selected_date = today.replace(day=1)
        
        # Calculer le premier et dernier jour du mois
        first_day = selected_date
        # Obtenir le dernier jour du mois
        if first_day.month == 12:
            last_day = date(first_day.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(first_day.year, first_day.month + 1, 1) - timedelta(days=1)
        
        # Convertir en datetime pour la recherche
        start_datetime = datetime.combine(first_day, datetime.min.time())
        end_datetime = datetime.combine(last_day, datetime.max.time())
        
        # Récupérer les créneaux de planning pour le mois
        _logger.info("Recherche de créneaux pour le mois du %s au %s", first_day, last_day)
        domain = [
            ('employee_id', '=', employee.id),
            '|', '|',
            '&', ('start_datetime', '>=', start_datetime), ('start_datetime', '<=', end_datetime),
            '&', ('end_datetime', '>=', start_datetime), ('end_datetime', '<=', end_datetime),
            '&', ('start_datetime', '<=', start_datetime), ('end_datetime', '>=', end_datetime),
        ]
        _logger.info("Domaine de recherche: %s", domain)
        
        planning_slots = request.env['planning.slot'].sudo().search(domain)
        _logger.info("Créneaux trouvés pour le mois: %s", planning_slots.ids)
        
        # Organiser les données pour l'affichage du calendrier
        cal = calendar.monthcalendar(first_day.year, first_day.month)
        weeks = []
        
        # Préparer les données pour chaque semaine du mois
        for week_days in cal:
            week = []
            for day_num in week_days:
                if day_num == 0:
                    # Jour hors du mois
                    week.append({
                        'day': 0,
                        'date': None,
                        'slots': [],
                        'is_today': False,
                        'has_slots': False,
                    })
                else:
                    # Créer la date pour ce jour
                    day_date = date(first_day.year, first_day.month, day_num)
                    
                    # Filtrer les créneaux pour ce jour
                    day_start = datetime.combine(day_date, datetime.min.time())
                    day_end = datetime.combine(day_date, datetime.max.time())
                    
                    day_slots = planning_slots.filtered(
                        lambda s: (s.start_datetime <= day_end and s.end_datetime >= day_start)
                    )
                    
                    week.append({
                        'day': day_num,
                        'date': day_date,
                        'slots': day_slots,
                        'is_today': day_date == today,
                        'has_slots': bool(day_slots),
                    })
            weeks.append(week)
        
        # Préparer les données pour la navigation
        if first_day.month == 1:
            prev_month = date(first_day.year - 1, 12, 1)
        else:
            prev_month = date(first_day.year, first_day.month - 1, 1)
            
        if first_day.month == 12:
            next_month = date(first_day.year + 1, 1, 1)
        else:
            next_month = date(first_day.year, first_day.month + 1, 1)
        
        values.update({
            'employee': employee,
            'planning_slots': planning_slots,
            'weeks': weeks,
            'month_name': selected_date.strftime('%B %Y'),
            'prev_month': prev_month.strftime('%Y-%m'),
            'next_month': next_month.strftime('%Y-%m'),
            'today': today,
            'date': selected_date.strftime('%Y-%m'),
            'page_name': 'planning_month',
            'default_url': '/my/planning/month',
        })
        
        return request.render("portal_planning.portal_my_planning_slots", values)
