# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountAnalyticLine(models.Model):
    """Extension du modèle account.analytic.line pour les fonctionnalités du portail planning."""
    _inherit = 'account.analytic.line'
    
    planning_slot_id = fields.Many2one(
        'planning.slot',
        string='Créneau de planning',
        help="Créneau de planning associé à cette entrée timesheet",
        index=True
    )
    portal_generated = fields.Boolean(
        string='Généré via le portail',
        default=False,
        help="Indique si cette entrée a été générée via le portail planning"
    )
    portal_confirmation_date = fields.Datetime(
        string='Date de confirmation',
        help="Date de la confirmation qui a généré cette entrée"
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la méthode create pour gérer la création d'entrées timesheet depuis le portail."""
        for vals in vals_list:
            # Si l'entrée est liée à un créneau de planning et générée via le portail
            if vals.get('planning_slot_id') and vals.get('portal_generated'):
                # Récupérer le créneau de planning
                slot = self.env['planning.slot'].browse(vals['planning_slot_id'])
                
                # Ajouter le projet et la tâche si disponibles
                if hasattr(slot, 'project_id') and slot.project_id:
                    vals['project_id'] = slot.project_id.id
                    if hasattr(slot, 'task_id') and slot.task_id:
                        vals['task_id'] = slot.task_id.id
                
                # Ajouter l'employé et l'utilisateur si non spécifiés
                if not vals.get('employee_id') and slot.employee_id:
                    vals['employee_id'] = slot.employee_id.id
                if not vals.get('user_id') and slot.employee_id.user_id:
                    vals['user_id'] = slot.employee_id.user_id.id
        
        return super(AccountAnalyticLine, self).create(vals_list)
    
    def unlink(self):
        """Surcharge de la méthode unlink pour empêcher la suppression d'entrées générées via le portail."""
        for line in self:
            if line.portal_generated and not self.env.user.has_group('planning.group_planning_manager'):
                raise models.UserError(_("Vous ne pouvez pas supprimer une entrée timesheet générée via le portail planning."))
        
        return super(AccountAnalyticLine, self).unlink()
