# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Queue Management for Bemade Synchronization.

This module extends the base synchronization queue to add Bemade-specific
functionality for managing the synchronization queue between Odoo instances.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class OdooToBemadeSyncQueue(models.Model):
    """Synchronization queue for Bemade Odoo instances.

    Extends the base synchronization queue to handle Bemade-specific
    synchronization operations.
    """

    _name = 'odoo.to.bemade.sync.queue'
    _description = 'Bemade Sync Queue Entry'
    _inherit = 'odoo.sync.queue'
    
    # Add Bemade-specific fields here
    bemade_instance_id = fields.Many2one(
        comodel_name='odoo.to.bemade.instance',
        string='Bemade Instance',
        help='The Bemade instance related to this queue entry',
    )
    
    @api.model
    def create_sync_job(self, instance_id, model_name, record_id, operation_type='create', priority=10):
        """Create a new synchronization job in the queue.

        Args:
            instance_id: ID of the Bemade instance to sync with
            model_name: Technical name of the model to synchronize
            record_id: ID of the record to synchronize
            operation_type: Type of operation (create, update, delete)
            priority: Priority of the job (lower number = higher priority)

        Returns:
            The created queue entry record
        """
        return self.create({
            'bemade_instance_id': instance_id,
            'model': model_name,
            'record_id': record_id,
            'operation_type': operation_type,
            'priority': priority,
            'state': 'pending',
        })
    
    def process_bemade_specific_logic(self):
        """Add Bemade-specific processing logic here.
        
        This method can be called during processing to handle any 
        Bemade-specific synchronization requirements.
        
        Returns:
            Boolean indicating success
        """
        self.ensure_one()
        # Implement Bemade-specific logic
        return True
