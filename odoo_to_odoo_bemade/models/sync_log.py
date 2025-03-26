# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Synchronization Log for Bemade.

This module extends the base synchronization log to add Bemade-specific
functionality for logging synchronization operations.
"""

import logging
import json
from datetime import datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class OdooToBemadeSyncLog(models.Model):
    """Synchronization log for Bemade operations.

    Extends the base synchronization log to handle Bemade-specific
    logging requirements.
    """

    _name = 'odoo.to.bemade.sync.log'
    _description = 'Bemade Sync Log Entry'
    _inherit = 'odoo.sync.log'
    _order = 'create_date desc'

    # Add Bemade-specific fields here
    bemade_instance_id = fields.Many2one(
        comodel_name='odoo.to.bemade.instance',
        string='Bemade Instance',
        help='The Bemade instance related to this log entry',
    )
    
    @api.model
    def log(self, operation, model=None, record_id=None, result='success', details=None, instance_id=None):
        """Create a log entry for a synchronization operation.

        Args:
            operation: Type of operation performed (create, update, delete, etc.)
            model: Technical name of the model that was synchronized
            record_id: ID of the record that was synchronized
            result: Result of the operation (success, error)
            details: Additional details or error message
            instance_id: ID of the Bemade instance involved

        Returns:
            The created log entry record
        """
        if details and not isinstance(details, str):
            details = json.dumps(details)
            
        return self.create({
            'operation': operation,
            'model': model,
            'record_id': record_id,
            'result': result,
            'details': details,
            'bemade_instance_id': instance_id,
        })
