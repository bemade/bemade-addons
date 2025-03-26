# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Journal de synchronisation pour Odoo to Bemade Customer.

Ce module enregistre toutes les opérations de synchronisation effectuées
entre Odoo client et Bemade pour des fins d'audit et de dépannage.
"""

from odoo import api, fields, models, _


class OdooToBemadeCustomerSyncLog(models.Model):
    """Journal des synchronisations.

    Enregistre toutes les opérations de synchronisation pour traçabilité.
    """

    _name = 'odoo.to.bemade.customer.sync.log'
    _description = 'Journal de synchronisation Bemade'
    _inherit = 'odoo.sync.log'
    _order = 'create_date desc'

    name = fields.Char(
        string='Opération',
        required=True,
    )
    model_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.sync.model',
        string='Modèle',
        ondelete='set null',
    )
    record_id = fields.Integer(
        string='ID Enregistrement',
    )
    operation = fields.Selection(
        selection=[
            ('sync', 'Synchronisation'),
            ('delete', 'Suppression'),
            ('conflict', 'Conflit'),
            ('error', 'Erreur'),
        ],
        string='Type d\'opération',
        required=True,
    )
    direction = fields.Selection(
        selection=[
            ('to_bemade', 'Odoo → Bemade'),
            ('from_bemade', 'Bemade → Odoo'),
        ],
        string='Direction',
    )
    result = fields.Selection(
        selection=[
            ('success', 'Succès'),
            ('warning', 'Avertissement'),
            ('error', 'Erreur'),
        ],
        string='Résultat',
        required=True,
    )
    execution_time = fields.Float(
        string='Temps d\'exécution (s)',
        digits=(10, 3),
    )
    details = fields.Text(
        string='Détails',
    )
    remote_id = fields.Char(
        string='ID Bemade',
    )
    queue_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.sync.queue',
        string='Entrée file d\'attente',
        ondelete='set null',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Utilisateur',
        default=lambda self: self.env.user.id,
        readonly=True,
    )

    def action_view_record(self):
        """Affiche l'enregistrement associé à cette entrée de journal."""
        self.ensure_one()
        if not self.model_id or not self.record_id:
            return False
            
        return {
            'name': _('Enregistrement synchronisé'),
            'type': 'ir.actions.act_window',
            'res_model': self.model_id.model,
            'res_id': self.record_id,
            'view_mode': 'form',
        }

    @api.model
    def log(self, operation, model=None, record_id=None, result='success', details=None, 
            direction=None, remote_id=None, queue_id=None, execution_time=0):
        """Crée une entrée dans le journal des synchronisations."""
        model_id = False
        if model and isinstance(model, str):
            model_rec = self.env['odoo.to.bemade.customer.sync.model'].search(
                [('model', '=', model)], limit=1)
            if model_rec:
                model_id = model_rec.id
        elif model and hasattr(model, 'id'):
            model_id = model.id
            
        name = f"{operation.capitalize()}"
        if model_id:
            model_name = self.env['odoo.to.bemade.customer.sync.model'].browse(model_id).name
            name += f" - {model_name}"
        if record_id:
            name += f" #{record_id}"
            
        vals = {
            'name': name,
            'model_id': model_id,
            'record_id': record_id,
            'operation': operation,
            'result': result,
            'details': details,
            'direction': direction,
            'remote_id': remote_id,
            'queue_id': queue_id and queue_id if isinstance(queue_id, int) else queue_id and queue_id.id,
            'execution_time': execution_time,
        }
        
        return self.create(vals)
