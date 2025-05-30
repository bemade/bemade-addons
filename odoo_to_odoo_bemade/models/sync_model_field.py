# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Field Synchronization Configuration for Bemade.

This module extends the base field synchronization configuration to add
Bemade-specific functionality for defining how fields are synchronized
between Odoo instances.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class OdooToBemadeSyncModelField(models.Model):
    """Bemade synchronization field configuration.

    Extends the base synchronization field configuration to handle
    Bemade-specific requirements for field synchronization.
    """

    _name = 'odoo.to.bemade.sync.model.field'
    _description = 'Bemade Synchronized Field'
    _inherit = 'odoo.sync.model.field'
    
    # Add Bemade-specific fields here
    bemade_transformation = fields.Selection([
        ('none', 'No Transformation'),
        ('prefix', 'Add Prefix'),
        ('suffix', 'Add Suffix'),
        ('replace', 'Find and Replace'),
        ('custom', 'Custom Python Code')
    ], string='Bemade Transformation', default='none',
       help='Bemade-specific transformation to apply to the field value')
    
    bemade_transform_value = fields.Char(
        string='Transformation Value',
        help='Value to use for the transformation (prefix, suffix, replacement, etc.)'
    )
    
    bemade_custom_code = fields.Text(
        string='Custom Python Code',
        help='Custom Python code to transform the field value'
    )
    
    @api.model
    def create_field_mapping(self, sync_model_id, source_field, target_field=None, active=True, transform_type='direct'):
        """Create a field mapping for synchronization.

        Args:
            sync_model_id: ID of the sync model configuration
            source_field: Name of the source field
            target_field: Name of the target field (defaults to source_field)
            active: Whether the mapping is active
            transform_type: Type of transformation to apply

        Returns:
            The created field mapping record
        """
        return self.create({
            'sync_model_id': sync_model_id,
            'source_field': source_field,
            'target_field': target_field or source_field,
            'active': active,
            'transform_type': transform_type,
            'bemade_transformation': 'none',
        })
        
    def apply_bemade_transformation(self, value, record):
        """Apply Bemade-specific transformations to the field value.
        
        Args:
            value: The original field value
            record: The record being synchronized
            
        Returns:
            The transformed value
        """
        self.ensure_one()
        
        if not value or self.bemade_transformation == 'none':
            return value
            
        if self.bemade_transformation == 'prefix':
            return f"{self.bemade_transform_value or ''}{value}"
            
        elif self.bemade_transformation == 'suffix':
            return f"{value}{self.bemade_transform_value or ''}"
            
        elif self.bemade_transformation == 'replace' and self.bemade_transform_value:
            # Format: "find:replace"
            parts = self.bemade_transform_value.split(':')
            if len(parts) >= 2:
                find_val = parts[0]
                replace_val = parts[1]
                return str(value).replace(find_val, replace_val)
                
        elif self.bemade_transformation == 'custom' and self.bemade_custom_code:
            # Execute custom code with appropriate safeguards
            try:
                # Create a safe local execution environment
                local_dict = {
                    'value': value,
                    'record': record,
                    'field': self,
                }
                
                # Execute the custom code
                exec(self.bemade_custom_code, {'__builtins__': {}}, local_dict)
                
                # Return the transformed value
                if 'result' in local_dict:
                    return local_dict['result']
                else:
                    _logger.warning("Custom transformation code did not set 'result' variable")
            except Exception as e:
                _logger.error("Error executing custom transformation: %s", str(e))
        
        return value
