# Copyright 2025 Codeium
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Model Synchronization Configuration.

This module defines how models are synchronized between Odoo instances.
It handles model mapping, field configuration, and synchronization rules
for each model that needs to be synchronized.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class OdooSyncModel(models.Model):
    _name = 'odoo.sync.model'
    _description = 'Synchronized Model'
    _order = 'priority, id'

    model_id = fields.Many2one(
        comodel_name='ir.model', 
        string='Source Model', 
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        related='model_id.model', 
        string='Technical Name',
        store=True
    )
    
    instance_id = fields.Many2one(
        comodel_name='odoo.sync.instance', 
        string='Remote Instance',
        required=True
    )

    target_model = fields.Char(
        string='Target Model',
        help='Technical name of the model on remote instance'
    )

    active = fields.Boolean(
        string='Active', 
        default=True
    )
    
    priority = fields.Integer(
        string='Priority',
        default=10,
        help='Synchronization order for dependencies'
    )
    
    field_ids = fields.One2many(
        comodel_name='odoo.sync.model.field', 
        inverse_name='model_sync_id', 
        string='Synchronized Fields'
    )

    _sql_constraints = [
        ('model_instance_uniq', 'unique(model_id, instance_id)', 
         'Un modèle ne peut être synchronisé qu\'une fois par instance!')
    ]

    @api.model
    def create(self, vals):
        if not vals.get('target_model') and vals.get('model_id'):
            # Par défaut, utiliser le même nom de modèle que la source
            model = self.env['ir.model'].browse(vals['model_id'])
            vals['target_model'] = model.model

        record = super().create(vals)

        # Créer automatiquement les champs de base
        if record.model_id:
            fields_to_sync = ['create_date', 'write_date', 'create_uid', 'write_uid']
            for field_name in fields_to_sync:
                field = self.env['ir.model.fields'].search([
                    ('model_id', '=', record.model_id.id),
                    ('name', '=', field_name)
                ])
                if field:
                    self.env['odoo.sync.model.field'].create({
                        'model_sync_id': record.id,
                        'field_id': field.id,
                        'required': True
                    })
        return record

    def name_get(self):
        return [(r.id, f'{r.name} → {r.instance_id.name}') for r in self]