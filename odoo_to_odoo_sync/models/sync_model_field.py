from odoo import models, fields, api

class OdooSyncModelField(models.Model):
    _name = 'odoo.sync.model.field'
    _description = 'Synchronized Field'

    model_sync_id = fields.Many2one(
        comodel_name='odoo.sync.model', 
        string='Synchronized Model',
        required=True, 
        ondelete='cascade'
    )
    
    field_id = fields.Many2one(
        comodel_name='ir.model.fields', 
        string='Field',
        domain="[('model_id', '=', parent.model_id)]",
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        related='field_id.name', 
        string='Technical Name', 
        store=True
    )

    required = fields.Boolean(
        string='Required', 
        default=False
    )

    sync_default = fields.Char(
        string='Default Value',
        help='Value to use if not available'
    )

    _sql_constraints = [
        ('field_uniq', 'unique(model_sync_id, field_id)', 
         'Un champ ne peut être synchronisé qu\'une fois par modèle!')
    ]
