# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools import float_round
from odoo.exceptions import UserError
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)
import logging

_logger = logging.getLogger(__name__)

class PlanningSlot(models.Model):
    """Extension du modèle planning.slot pour les fonctionnalités du portail."""
    _inherit = 'planning.slot'
    
    # Champs pour la modification via le portail
    portal_can_modify = fields.Boolean(
        string='Modifiable via le portail',
        default=True,
        help="Si coché, l'utilisateur du portail peut modifier ce créneau"
    )
    portal_modified = fields.Boolean(
        string='Modifié via le portail',
        default=False,
        copy=False,
        help="Indique si le créneau a été modifié via le portail"
    )
    portal_modification_date = fields.Datetime(
        string='Date de modification',
        copy=False,
        help="Date de la dernière modification via le portail"
    )
    portal_modification_user_id = fields.Many2one(
        'res.users',
        string='Modifié par',
        copy=False,
        help="Utilisateur ayant effectué la dernière modification"
    )
    portal_modification_approved = fields.Selection([
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Refusé')
    ], string='Statut de modification', default=False, copy=False)
    portal_modification_notes = fields.Text(
        string='Notes de modification',
        copy=False,
        help="Notes concernant la modification"
    )
    portal_original_start = fields.Datetime(
        string='Début original',
        copy=False,
        help="Date de début originale avant modification"
    )
    portal_original_end = fields.Datetime(
        string='Fin originale',
        copy=False,
        help="Date de fin originale avant modification"
    )
    portal_original_role_id = fields.Many2one(
        'planning.role',
        string='Rôle original',
        copy=False,
        help="Rôle original avant modification"
    )
    
    # Champs pour la création via le portail
    portal_created = fields.Boolean(
        string='Créé via le portail',
        default=False,
        copy=False,
        help="Indique si le créneau a été créé via le portail"
    )
    portal_creation_date = fields.Datetime(
        string='Date de création',
        copy=False,
        help="Date de création via le portail"
    )
    portal_creation_user_id = fields.Many2one(
        'res.users',
        string='Créé par',
        copy=False,
        help="Utilisateur ayant créé le créneau"
    )
    portal_creation_approved = fields.Selection([
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Refusé')
    ], string='Statut de création', default=False, copy=False)
    portal_creation_notes = fields.Text(
        string='Notes de création',
        copy=False,
        help="Notes concernant la création"
    )
    
    # Champs pour la confirmation via le portail
    portal_confirmed = fields.Boolean(
        string='Confirmé via le portail',
        default=False,
        copy=False,
        help="Indique si le créneau a été confirmé via le portail"
    )
    portal_confirmation_date = fields.Datetime(
        string='Date de confirmation',
        copy=False,
        help="Date de confirmation via le portail"
    )
    
    # Champs pour les timesheets générés
    timesheet_ids = fields.One2many(
        'account.analytic.line',
        'planning_slot_id',
        string='Feuilles de temps',
        copy=False,
        help="Feuilles de temps générées pour ce créneau"
    )
    
    # Champs calculés
    portal_status = fields.Selection([
        ('draft', 'À confirmer'),
        ('confirmed', 'Confirmé'),
        ('modified', 'Modifié'),
        ('pending_approval', 'En attente d\'approbation')
    ], string='Statut portail', compute='_compute_portal_status', store=True)
    
    @api.depends('state', 'portal_confirmed', 'portal_modified', 'portal_modification_approved', 'portal_created', 'portal_creation_approved')
    def _compute_portal_status(self):
        """Calcule le statut du créneau pour l'affichage dans le portail."""
        for slot in self:
            if slot.portal_created and slot.portal_creation_approved == 'pending':
                slot.portal_status = 'pending_approval'
            elif slot.portal_modified and slot.portal_modification_approved == 'pending':
                slot.portal_status = 'pending_approval'
            elif slot.portal_confirmed:
                slot.portal_status = 'confirmed'
            elif slot.portal_modified:
                slot.portal_status = 'modified'
            else:
                slot.portal_status = 'draft'
    
    def action_confirm_portal(self):
        """Confirme le créneau via le portail."""
        self.ensure_one()
        if self.state != 'published':
            return False
        
        self.write({
            'portal_confirmed': True,
            'portal_confirmation_date': fields.Datetime.now(),
            'state': 'published'  # Assure que l'état reste publié
        })
        
        # Générer les timesheets si le paramètre est activé
        auto_generate_timesheet = self.env['ir.config_parameter'].sudo().get_param('portal_planning.auto_generate_timesheet', True)
        if auto_generate_timesheet and self.employee_id:
            self._generate_timesheet()
        
        # Envoyer une notification au responsable
        if hasattr(self, 'message_post'):
            self.message_post(
                body=_('Créneau confirmé via le portail par %s') % (self.employee_id.name),
                message_type='notification',
                subtype_id=self.env.ref('mail.mt_note').id
            )
        
        return True
    
    def action_modify_portal(self, vals):
        """Modifie le créneau via le portail."""
        self.ensure_one()
        if not self.portal_can_modify:
            return False
        
        # Sauvegarder les valeurs originales avant modification
        original_vals = {
            'portal_original_start': self.start_datetime,
            'portal_original_end': self.end_datetime,
            'portal_original_role_id': self.role_id.id,
            'portal_modified': True,
            'portal_modification_date': fields.Datetime.now(),
            'portal_modification_user_id': self.env.user.id,
        }
        
        # Vérifier si la modification nécessite une approbation
        auto_approve = self.env['ir.config_parameter'].sudo().get_param('portal_planning.auto_approve_modifications', False)
        has_auto_approve = False
        if self.employee_id and self.employee_id.resource_id and hasattr(self.employee_id.resource_id, 'portal_auto_approve_modifications'):
            has_auto_approve = self.employee_id.resource_id.portal_auto_approve_modifications
        if auto_approve or has_auto_approve:
            original_vals['portal_modification_approved'] = 'approved'
            # Mettre à jour les valeurs du créneau
            update_vals = {**vals, **original_vals}
            self.write(update_vals)
        else:
            original_vals['portal_modification_approved'] = 'pending'
            # Sauvegarder les valeurs originales mais ne pas mettre à jour le créneau
            self.write(original_vals)
            
            # Créer une entrée dans le modèle de modification pour suivi
            self.env['portal.planning.modification'].sudo().create({
                'slot_id': self.id,
                'user_id': self.env.user.id,
                'date': fields.Datetime.now(),
                'old_start': self.start_datetime,
                'old_end': self.end_datetime,
                'old_role_id': self.role_id.id,
                'new_start': vals.get('start_datetime', self.start_datetime),
                'new_end': vals.get('end_datetime', self.end_datetime),
                'new_role_id': vals.get('role_id', self.role_id.id),
                'state': 'pending',
                'notes': vals.get('portal_modification_notes', '')
            })
        
        # Envoyer un message dans le chatter si le module mail est installé
        if hasattr(self, 'message_post'):
            self.message_post(
                body=_('Créneau modifié via le portail par %s') % (self.employee_id.name),
                message_type='notification',
                subtype_id=self.env.ref('mail.mt_note').id
            )
        
        return True
    
    def _generate_timesheet(self):
        """Génère les entrées timesheet pour ce créneau."""
        self.ensure_one()
        
        # Vérifier si le module timesheet est installé
        if 'account.analytic.line' not in self.env:
            return False
        
        # Vérifier si l'employé a un utilisateur associé
        if not hasattr(self, 'employee_id') or not self.employee_id or not self.employee_id.user_id:
            return False
        
        # Vérifier si des entrées timesheet existent déjà pour ce créneau
        AnalyticLine = self.env['account.analytic.line'].sudo()
        
        # Vérifier les champs disponibles dans le modèle account.analytic.line
        analytic_fields = AnalyticLine._fields
        date_field = 'date' if 'date' in analytic_fields else False
        employee_field = 'employee_id' if 'employee_id' in analytic_fields else False
        project_field = 'project_id' if 'project_id' in analytic_fields else False
        
        if not date_field or not employee_field:
            return False
        
        # Construire le domaine de recherche en fonction des champs disponibles
        domain = []
        if date_field and hasattr(self, 'start_datetime'):
            domain.append((date_field, '>=', self.start_datetime.date()))
        if date_field and hasattr(self, 'end_datetime'):
            domain.append((date_field, '<=', self.end_datetime.date()))
        if employee_field and hasattr(self, 'employee_id'):
            domain.append((employee_field, '=', self.employee_id.id))
        if project_field:
            domain.append((project_field, '!=', False))
        
        existing_timesheets = AnalyticLine.search(domain) if domain else AnalyticLine
        
        # Pour simplifier, nous créons une entrée timesheet pour la durée totale du créneau
        # Une implémentation plus complexe pourrait gérer les chevauchements partiels
        if not existing_timesheets:
            # Créer une nouvelle entrée timesheet
            timesheet_vals = {
                'name': self.name or _('Créneau de planning'),
                'planning_slot_id': self.id,
                'portal_generated': True,
                'portal_confirmation_date': self.portal_confirmation_date,
            }
            
            # Ajouter les champs disponibles
            if date_field and hasattr(self, 'start_datetime'):
                timesheet_vals[date_field] = self.start_datetime.date()
            if 'unit_amount' in analytic_fields and hasattr(self, 'allocated_hours'):
                timesheet_vals['unit_amount'] = self.allocated_hours
            if employee_field and hasattr(self, 'employee_id'):
                timesheet_vals[employee_field] = self.employee_id.id
            if 'user_id' in analytic_fields and hasattr(self, 'employee_id') and self.employee_id.user_id:
                timesheet_vals['user_id'] = self.employee_id.user_id.id
            
            # Ajouter le projet et la tâche si disponibles
            # Vérifier si le module project est installé et si les champs sont disponibles
            if project_field and self.env.registry.get('project.project'):
                # Vérifier si le modèle planning.slot a un champ project_id
                slot_fields = self._fields
                if 'project_id' in slot_fields and hasattr(self, 'project_id'):
                    project_id = getattr(self, 'project_id', False)
                    if project_id:
                        timesheet_vals[project_field] = project_id.id
                        if 'task_id' in analytic_fields and hasattr(self, 'task_id'):
                            task_id = getattr(self, 'task_id', False)
                            if task_id:
                                timesheet_vals['task_id'] = task_id.id
            
            # Créer l'entrée timesheet
            try:
                timesheet = AnalyticLine.create(timesheet_vals)
                return timesheet
            except (ValueError, UserError) as e:
                # Log l'erreur mais ne pas interrompre le processus
                _logger.error("Erreur lors de la création de l'entrée timesheet: %s", str(e))
            except Exception as e:
                # Log l'erreur plus grave mais ne pas interrompre le processus
                _logger.error("Erreur inattendue lors de la création de l'entrée timesheet: %s", str(e))
                return False
        
        return True
