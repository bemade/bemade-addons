# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_task_deadline_cascade = fields.Boolean(
        string='Enable Task Deadline Cascade',
        config_parameter='project_task_date_deadline_cascade_update.enablecascade'
    )
