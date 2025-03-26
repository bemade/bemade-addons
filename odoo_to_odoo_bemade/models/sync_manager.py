# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Synchronization Manager for Bemade.

This module extends the base synchronization manager to add Bemade-specific
functionality for managing synchronization operations between Odoo instances.
"""

import logging
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class OdooToBemadeSyncManager(models.Model):
    """Synchronization manager for Bemade.

    Extends the base synchronization manager to handle Bemade-specific
    synchronization requirements.
    """

    _name = 'odoo.to.bemade.sync.manager'
    _description = 'Bemade Sync Manager'
    _inherit = 'odoo.sync.manager'
    
    # Add Bemade-specific fields here
    bemade_sync_enabled = fields.Boolean(
        string='Enable Bemade Sync',
        default=True,
        help='Enable synchronization with Bemade instances',
    )
    
    @api.model
    def cron_process_sync_queue(self):
        """Process pending synchronization queue entries.
        
        This method is called by a scheduled action to process
        pending queue entries for Bemade synchronization.
        
        Returns:
            Boolean indicating success
        """
        if not self.env['ir.config_parameter'].sudo().get_param('odoo_to_odoo_bemade.sync_enabled', True):
            _logger.info("Bemade synchronization is disabled in system parameters")
            return False
            
        # Get active instances
        active_instances = self.env['odoo.to.bemade.instance'].search([
            ('active', '=', True),
            ('state', '=', 'connected')
        ])
        
        if not active_instances:
            _logger.info("No active and connected Bemade instances found")
            return False
            
        # Process queue entries for each active instance
        for instance in active_instances:
            self._process_queue_for_instance(instance)
            
        return True
    
    def _process_queue_for_instance(self, instance):
        """Process queue entries for a specific Bemade instance.
        
        Args:
            instance: The Bemade instance to process queue entries for
            
        Returns:
            Boolean indicating success
        """
        # Get pending queue entries for this instance
        queue_entries = self.env['odoo.to.bemade.sync.queue'].search([
            ('bemade_instance_id', '=', instance.id),
            ('state', '=', 'pending'),
            '|',
            ('next_retry', '=', False),
            ('next_retry', '<=', fields.Datetime.now())
        ], order='priority, id', limit=50)
        
        if not queue_entries:
            _logger.info("No pending queue entries for Bemade instance %s", instance.name)
            return False
            
        # Process each queue entry
        for entry in queue_entries:
            try:
                self._process_queue_entry(entry, instance)
            except Exception as e:
                self.env['odoo.to.bemade.sync.log'].log(
                    operation=entry.operation_type,
                    model=entry.model,
                    record_id=entry.record_id,
                    result='error',
                    details=str(e),
                    instance_id=instance.id
                )
                
                # Update entry with error information
                retry_count = entry.retry_count + 1
                max_retries = int(self.env['ir.config_parameter'].sudo().get_param('odoo_to_odoo_bemade.max_retries', 5))
                
                if retry_count >= max_retries:
                    entry.write({
                        'state': 'failed',
                        'retry_count': retry_count,
                        'error_message': str(e)
                    })
                else:
                    # Exponential backoff for retries
                    delay_minutes = 5 * (2 ** (retry_count - 1))
                    next_retry = fields.Datetime.now() + timedelta(minutes=delay_minutes)
                    
                    entry.write({
                        'state': 'pending',
                        'retry_count': retry_count,
                        'error_message': str(e),
                        'next_retry': next_retry
                    })
        
        return True
    
    def _process_queue_entry(self, entry, instance):
        """Process a single queue entry.
        
        Args:
            entry: The queue entry to process
            instance: The Bemade instance to process the entry for
            
        Returns:
            Boolean indicating success
        """
        # Mark the entry as being processed
        entry.write({'state': 'processing'})
        
        # Process based on operation type
        if entry.operation_type == 'create':
            result = self._sync_create(entry, instance)
        elif entry.operation_type == 'update':
            result = self._sync_update(entry, instance)
        elif entry.operation_type == 'delete':
            result = self._sync_delete(entry, instance)
        else:
            raise UserError(_("Unknown operation type: %s") % entry.operation_type)
        
        # Process Bemade-specific logic
        entry.process_bemade_specific_logic()
        
        # Mark the entry as processed
        entry.write({'state': 'done'})
        
        # Log success
        self.env['odoo.to.bemade.sync.log'].log(
            operation=entry.operation_type,
            model=entry.model,
            record_id=entry.record_id,
            result='success',
            instance_id=instance.id
        )
        
        return True
    
    def _sync_create(self, entry, instance):
        """Synchronize a record creation.
        
        Args:
            entry: The queue entry to process
            instance: The Bemade instance to sync with
            
        Returns:
            The result of the create operation
        """
        # Get the model and record
        model = self.env[entry.model]
        record = model.browse(entry.record_id)
        
        # Get the connection to the remote instance
        connection = instance.get_connection()
        
        # Map record data to target model fields
        sync_model = self.env['odoo.sync.model'].search([
            ('name', '=', entry.model),
            ('instance_id', '=', instance.id)
        ], limit=1)
        
        if not sync_model:
            raise UserError(_("No synchronization configuration found for model %s on instance %s") % 
                           (entry.model, instance.name))
        
        # Prepare the data for the remote instance
        # This would involve mapping fields from the local model to the remote model
        # based on the configuration in sync_model and its fields
        remote_data = self._prepare_remote_data(record, sync_model)
        
        # Create the record on the remote instance
        target_model = sync_model.target_model or entry.model
        result = connection.create(target_model, remote_data)
        
        return result
    
    def _sync_update(self, entry, instance):
        """Synchronize a record update.
        
        Args:
            entry: The queue entry to process
            instance: The Bemade instance to sync with
            
        Returns:
            The result of the update operation
        """
        # Implementation similar to _sync_create, but for updates
        # Get the model and record
        model = self.env[entry.model]
        record = model.browse(entry.record_id)
        
        # Get the connection to the remote instance
        connection = instance.get_connection()
        
        # Map record data to target model fields
        sync_model = self.env['odoo.sync.model'].search([
            ('name', '=', entry.model),
            ('instance_id', '=', instance.id)
        ], limit=1)
        
        if not sync_model:
            raise UserError(_("No synchronization configuration found for model %s on instance %s") % 
                           (entry.model, instance.name))
        
        # Prepare the data for the remote instance
        remote_data = self._prepare_remote_data(record, sync_model)
        
        # Get the remote ID
        remote_id = self._get_remote_id(record, sync_model, instance)
        
        # Update the record on the remote instance
        target_model = sync_model.target_model or entry.model
        result = connection.write(target_model, remote_id, remote_data)
        
        return result
    
    def _sync_delete(self, entry, instance):
        """Synchronize a record deletion.
        
        Args:
            entry: The queue entry to process
            instance: The Bemade instance to sync with
            
        Returns:
            The result of the delete operation
        """
        # Get the connection to the remote instance
        connection = instance.get_connection()
        
        # Map record data to target model fields
        sync_model = self.env['odoo.sync.model'].search([
            ('name', '=', entry.model),
            ('instance_id', '=', instance.id)
        ], limit=1)
        
        if not sync_model:
            raise UserError(_("No synchronization configuration found for model %s on instance %s") % 
                           (entry.model, instance.name))
        
        # Get the remote ID
        # Since the record might already be deleted locally, we need to get the remote ID
        # from a mapping table or some other mechanism
        remote_id = self._get_remote_id_for_deleted_record(entry.record_id, sync_model, instance)
        
        # Delete the record on the remote instance
        target_model = sync_model.target_model or entry.model
        result = connection.unlink(target_model, remote_id)
        
        return result
    
    def _prepare_remote_data(self, record, sync_model):
        """Prepare record data for the remote instance.
        
        Args:
            record: The record to prepare data for
            sync_model: The synchronization model configuration
            
        Returns:
            Dictionary of field values for the remote instance
        """
        # Get the field mappings from the sync model
        field_mappings = self.env['odoo.sync.model.field'].search([
            ('sync_model_id', '=', sync_model.id)
        ])
        
        remote_data = {}
        
        # Apply field mappings
        for mapping in field_mappings:
            source_field = mapping.source_field
            target_field = mapping.target_field or source_field
            
            # Get the value from the source field
            value = record[source_field]
            
            # Apply any transformations defined in the mapping
            # This is a simplified example - real implementation would handle
            # complex field types, relationships, etc.
            if mapping.transform_type == 'direct':
                remote_data[target_field] = value
            elif mapping.transform_type == 'function':
                # Call a function to transform the value
                transform_method = getattr(self, mapping.transform_function, None)
                if transform_method:
                    remote_data[target_field] = transform_method(value, record, mapping)
                else:
                    _logger.warning("Transform function %s not found", mapping.transform_function)
                    remote_data[target_field] = value
        
        return remote_data
    
    def _get_remote_id(self, record, sync_model, instance):
        """Get the ID of the record on the remote instance.
        
        Args:
            record: The local record
            sync_model: The synchronization model configuration
            instance: The remote instance
            
        Returns:
            ID of the record on the remote instance
        """
        # In a real implementation, this would involve looking up the remote ID
        # from a mapping table or using an external ID mechanism
        # This is just a placeholder implementation
        return record.id  # Simplified - in reality would be a different ID
    
    def _get_remote_id_for_deleted_record(self, record_id, sync_model, instance):
        """Get the ID of a deleted record on the remote instance.
        
        Args:
            record_id: The local record ID
            sync_model: The synchronization model configuration
            instance: The remote instance
            
        Returns:
            ID of the record on the remote instance
        """
        # Similar to _get_remote_id but for records that have been deleted locally
        return record_id  # Simplified - in reality would be a different ID
    
    def sync_all(self):
        """Synchronize all active models with Bemade instances.
        
        Returns:
            Boolean indicating success
        """
        # Get active instances
        active_instances = self.env['odoo.to.bemade.instance'].search([
            ('active', '=', True),
            ('state', '=', 'connected')
        ])
        
        if not active_instances:
            raise UserError(_("No active and connected Bemade instances found"))
        
        # Get active sync models
        active_models = self.env['odoo.sync.model'].search([
            ('active', '=', True),
            ('instance_id', 'in', active_instances.ids)
        ])
        
        if not active_models:
            raise UserError(_("No active synchronization models configured"))
        
        # Synchronize each model
        for sync_model in active_models:
            model = self.env[sync_model.name]
            instance = sync_model.instance_id
            
            # Get records to synchronize
            # This is a simplified approach - in a real implementation,
            # you would need to handle determining which records need to be synced
            records = model.search([])
            
            # Create queue entries for each record
            queue = self.env['odoo.to.bemade.sync.queue']
            for record in records:
                queue.create_sync_job(
                    instance_id=instance.id,
                    model_name=sync_model.name,
                    record_id=record.id,
                    operation_type='update'  # Assuming update for existing records
                )
        
        return True
