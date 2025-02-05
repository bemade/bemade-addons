# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo import _

class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model
    def write(self, vals):
        res = super(ProjectTask, self).write(vals)
        if 'date_deadline' in vals:
            for task in self:
                if task.child_ids:
                    return {
                        'name': _('Update Deadline'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'update.deadline.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {'active_ids': self.ids},
                    }
        return res
