# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class ProjectTask(models.Model):
    _inherit = 'project.task'
    

    def _update_child_dates_recursive(self, date_deadline=None, planned_date_begin=None):
        """Update dates for all subtasks at all levels using _get_all_subtasks.
        
        Args:
            date_deadline: The deadline date to set for all subtasks
            planned_date_begin: The planned start date to set for all subtasks
        """
        if not self.child_ids:
            return
            
        _logger.debug(
            'Starting update for all subtasks of: %s (ID: %s)',
            self.name, self.id
        )
        
        # Get all subtasks at all levels
        all_subtasks = self._get_all_subtasks()
        
        if all_subtasks:
            # Update both dates for all subtasks at once
            values = {
                'date_deadline': date_deadline,
                'planned_date_begin': planned_date_begin
            }
            _logger.debug(
                'Updating %d subtasks with values: %s',
                len(all_subtasks), values
            )
            all_subtasks.write(values)

    @api.onchange('date_deadline')
    def _onchange_date_deadline(self):
        """When parent task deadline changes, update all child tasks deadlines and planned dates recursively."""
        if self.date_deadline and self.child_ids and not self.env.context.get('skip_onchange'):
            _logger.debug('Recursively updating deadline and planned date for all subtasks of: %s', self.name)
            self.with_context(skip_onchange=True)._update_child_dates_recursive(
                date_deadline=self.date_deadline,
                planned_date_begin=self.planned_date_begin  # Always pass planned_date_begin
            )

    def write(self, vals):
        """Override write to handle date updates from calendar view and form view.
        
        The calendar view updates dates through write instead of onchange.
        This ensures the cascade update works in both cases.
        """
        result = super().write(vals)
        
        # Check if date_deadline or planned_date_begin was updated
        if ('date_deadline' in vals or 'planned_date_begin' in vals) and not self.env.context.get('skip_write'):
            for task in self:
                if task.child_ids:
                    _logger.debug('Write: Recursively updating dates for all subtasks of: %s', task.name)
                    task.with_context(skip_write=True)._update_child_dates_recursive(
                        date_deadline=task.date_deadline,
                        planned_date_begin=task.planned_date_begin
                    )
        return result

    @api.onchange('planned_date_begin')
    def _onchange_planned_date_begin(self):
        """When parent task planned date changes, update all child tasks planned dates and deadlines recursively."""
        if self.planned_date_begin and self.child_ids and not self.env.context.get('skip_onchange'):
            _logger.debug('Recursively updating planned date and deadline for all subtasks of: %s', self.name)
            self.with_context(skip_onchange=True)._update_child_dates_recursive(
                planned_date_begin=self.planned_date_begin,
                date_deadline=self.date_deadline  # Always pass date_deadline
            )
