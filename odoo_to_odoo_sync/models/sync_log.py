# Copyright 2025 Codeium
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Synchronization Logging System.

This module implements the logging system for synchronization operations.
It tracks all synchronization attempts, their outcomes, and any errors
that occur during the process, providing a complete audit trail.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class OdooSyncLog(models.Model):
    _name = 'odoo.sync.log'
    _description = 'Synchronization Log'
    _order = 'create_date desc'

    name = fields.Char(
        string='Name', 
        compute='_compute_name'
    )
    queue_id = fields.Many2one(
        comodel_name='odoo.sync.queue', 
        string='Queue Entry', 
        required=True, 
        ondelete='cascade'
    )
    state = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('error', 'Error')
        ], 
        required=True
    )
    message = fields.Text(
        string='Message'
    )
    details = fields.Text(
        string='Technical Details'
    )

    @api.depends('queue_id', 'state')
    def _compute_name(self):
        for record in self:
            record.name = f'{record.queue_id.name} - {record.state}'
