# -*- coding: utf-8 -*-

from odoo import api, fields, models


class UpdateDeadlineWizard(models.TransientModel):
    _name = 'update.deadline.wizard'
    _description = 'Update Deadline Wizard'

    apply_to_children = fields.Boolean(string='Apply to Child Tasks', default=False)

    def update_deadline(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', [])
        tasks = self.env['project.task'].browse(active_ids)
        for task in tasks:
            if task.child_ids and self.apply_to_children:
                task.child_ids.write({'date_deadline': task.date_deadline})
