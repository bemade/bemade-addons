# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Queue de synchronisation pour Odoo to Bemade Customer.

Ce module gère la file d'attente des opérations de synchronisation
entre Odoo client et Bemade.
"""

from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class OdooToBemadeCustomerSyncQueue(models.Model):
    """File d'attente de synchronisation.

    Gère les opérations de synchronisation en file d'attente entre Odoo client et Bemade.
    """

    _name = 'odoo.to.bemade.customer.sync.queue'
    _description = 'File d\'attente de synchronisation Bemade'
    _inherit = 'odoo.sync.queue'
    _order = 'priority desc, create_date'

    name = fields.Char(
        string='Nom',
        compute='_compute_name',
        store=True,
    )
    model_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.sync.model',
        string='Modèle',
        required=True,
        ondelete='cascade',
    )
    record_id = fields.Integer(
        string='ID Enregistrement',
        required=True,
    )
    operation = fields.Selection(
        selection=[
            ('sync', 'Synchroniser'),
            ('delete', 'Supprimer'),
        ],
        default='sync',
        string='Opération',
        required=True,
    )
    state = fields.Selection(
        selection=[
            ('pending', 'En attente'),
            ('processing', 'En cours'),
            ('done', 'Terminé'),
            ('error', 'Erreur'),
        ],
        default='pending',
        string='État',
    )
    priority = fields.Integer(
        string='Priorité',
        default=10,
        help='Priorité de l\'opération (les valeurs plus élevées sont prioritaires)',
    )
    retry_count = fields.Integer(
        string='Tentatives',
        default=0,
    )
    max_retries = fields.Integer(
        string='Tentatives max',
        default=3,
    )
    error_message = fields.Text(
        string='Message d\'erreur',
    )
    next_retry = fields.Datetime(
        string='Prochaine tentative',
    )
    result = fields.Text(
        string='Résultat',
    )
    execution_time = fields.Float(
        string='Temps d\'exécution (s)',
        digits=(10, 3),
    )

    @api.depends('model_id', 'record_id', 'operation')
    def _compute_name(self):
        """Génère un nom descriptif pour l'entrée de la file d'attente."""
        for queue in self:
            if queue.model_id and queue.record_id:
                queue.name = f"{queue.operation} - {queue.model_id.name} #{queue.record_id}"
            else:
                queue.name = f"Nouvelle entrée {queue.id}"

    def action_reset(self):
        """Réinitialise une entrée de file d'attente en erreur à l'état en attente."""
        return self.write({
            'state': 'pending',
            'retry_count': 0,
            'error_message': False,
            'next_retry': False
        })

    def action_cancel(self):
        """Annule une entrée de file d'attente."""
        return self.unlink()

    def action_retry_now(self):
        """Force la tentative immédiate de traitement d'une entrée en erreur."""
        self.ensure_one()
        self.write({
            'state': 'pending',
            'next_retry': fields.Datetime.now(),
        })
        return self.env['odoo.to.bemade.customer.sync.manager'].process_queue(queue_ids=self.ids)
