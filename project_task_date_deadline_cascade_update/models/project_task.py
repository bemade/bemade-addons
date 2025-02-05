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
            
        _logger.info(
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
            _logger.info(
                'Updating %d subtasks with values: %s',
                len(all_subtasks), values
            )
            all_subtasks.write(values)

    @api.onchange('date_deadline')
    def _onchange_date_deadline(self):
        """When parent task deadline changes, update all child tasks deadlines and planned dates recursively."""
        if self.date_deadline and self.child_ids and not self.env.context.get('skip_onchange'):
            _logger.info('Recursively updating deadline and planned date for all subtasks of: %s', self.name)
            self.with_context(skip_onchange=True)._update_child_dates_recursive(
                date_deadline=self.date_deadline,
                planned_date_begin=self.planned_date_begin  # Always pass planned_date_begin
            )

    @api.onchange('planned_date_begin')
    def _onchange_planned_date_begin(self):
        """When parent task planned date changes, update all child tasks planned dates and deadlines recursively."""
        if self.planned_date_begin and self.child_ids and not self.env.context.get('skip_onchange'):
            _logger.info('Recursively updating planned date and deadline for all subtasks of: %s', self.name)
            self.with_context(skip_onchange=True)._update_child_dates_recursive(
                planned_date_begin=self.planned_date_begin,
                date_deadline=self.date_deadline  # Always pass date_deadline
            )
