# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Model Synchronization Configuration for Bemade.

This module extends the base model synchronization configuration to add
Bemade-specific functionality for defining how models are synchronized
between Odoo instances.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class OdooToBemadeSyncModel(models.Model):
    """Bemade synchronization model configuration.

    Extends the base synchronization model configuration to handle
    Bemade-specific requirements for model synchronization.
    """

    _name = 'odoo.to.bemade.sync.model'
    _description = 'Bemade Synchronized Model'
    _inherit = 'odoo.sync.model'
    
    # Add Bemade-specific fields here
    bemade_specific_setting = fields.Boolean(
        string='Bemade Specific Setting',
        default=False,
        help='Enable this for Bemade-specific synchronization behavior',
    )

    bemade_instance_id = fields.Many2one(
        comodel_name='odoo.to.bemade.instance',
        string='Bemade Instance',
        required=True,
        help='The Bemade instance this model will be synchronized with',
    )
    
    @api.model
    def create_sync_configuration(self, model_name, instance_id, target_model=None, active=True):
        """Create a synchronization configuration for a model.

        Args:
            model_name: Technical name of the model to synchronize
            instance_id: ID of the Bemade instance to sync with
            target_model: Technical name of the model on the remote instance
            active: Whether the synchronization is active

        Returns:
            The created model configuration record
        """
        # Find the ir.model record for the model name
        ir_model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
        if not ir_model:
            raise UserError(_("Model %s does not exist") % model_name)
            
        # Create the sync model configuration
        return self.create({
            'model_id': ir_model.id,
            'bemade_instance_id': instance_id,
            'instance_id': instance_id,  # For the inherited field
            'target_model': target_model or model_name,
            'active': active,
        })
        
    def generate_field_mappings(self):
        """Generate field mappings based on model fields.
        
        This method creates sync.model.field records for all the fields
        in the model that should be synchronized.
        
        Returns:
            List of created field mapping records
        """
        self.ensure_one()
        
        # Get the model
        model = self.env[self.name]
        model_fields = model._fields
        
        # Create field mappings for each relevant field
        field_mapping_model = self.env['odoo.to.bemade.sync.model.field']
        created_mappings = []
        
        for field_name, field in model_fields.items():
            # Skip fields that shouldn't be synchronized
            if field.type in ['one2many', 'many2many']:
                continue
                
            if field_name in ['id', 'create_uid', 'create_date', 'write_uid', 'write_date', '__last_update']:
                continue
                
            # Create a field mapping
            mapping = field_mapping_model.create({
                'sync_model_id': self.id,
                'source_field': field_name,
                'target_field': field_name,
                'active': True,
                'transform_type': 'direct',
            })
            
            created_mappings.append(mapping)
            
        return created_mappings
