# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Field Synchronization Configuration for Bemade clients.

This module defines how fields are synchronized between client instances
and the Bemade platform. It simplifies field mapping and transformations
for Bemade customers.
"""

import logging
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class OdooToBemadeCustomerSyncModelField(models.Model):
    """Champ de modèle synchronisé avec Bemade."""

    _name = 'odoo.to.bemade.customer.sync.model.field'
    _description = 'Champ de modèle synchronisé avec Bemade'
    _inherit = 'odoo.sync.model.field'

    sync_model_id = fields.Many2one(
        comodel_name='odoo.to.bemade.customer.sync.model',
        string='Modèle synchronisé',
        required=True,
        ondelete='cascade',
        help='Modèle auquel ce champ appartient',
    )
    
    field_name = fields.Char(
        string='Nom du champ',
        required=True,
        help='Nom technique du champ dans le modèle local (ex: name)'
    )
    
    bemade_field_name = fields.Char(
        string='Nom du champ Bemade',
        required=True,
        help='Nom technique du champ correspondant chez Bemade'
    )
    
    is_identifier = fields.Boolean(
        string='Est un identifiant',
        default=False,
        help='Indique si ce champ est utilisé pour identifier l\'enregistrement chez Bemade'
    )
    
    transform_type = fields.Selection(
        selection=[
            ('none', 'Aucune transformation'),
            ('function', 'Fonction Python'),
            ('mapping', 'Mapping de valeurs')
        ],
        string='Type de transformation',
        default='none',
        required=True,
        help='Type de transformation à appliquer au champ lors de la synchronisation'
    )
    
    transform_mapping = fields.Text(
        string='Mapping de transformation',
        help='Mapping JSON pour la transformation des valeurs (format: {"valeur_source": "valeur_cible",...})'
    )
    
    transform_function = fields.Text(
        string='Fonction de transformation',
        help='Code Python pour transformer la valeur (doit retourner la valeur transformée)'
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
        help='Indique si ce champ est activement synchronisé'
    )
    
    @api.constrains('transform_mapping')
    def _check_transform_mapping_json(self):
        """Vérifie que le mapping de transformation est un JSON valide."""
        for record in self:
            if record.transform_mapping:
                try:
                    json.loads(record.transform_mapping)
                except json.JSONDecodeError:
                    raise ValidationError(_("Le mapping de transformation doit être un JSON valide"))
    
    def transform_value(self, value):
        """Transforme une valeur selon la configuration du champ."""
        self.ensure_one()
        
        if self.transform_type == 'none' or value is False:
            return value
            
        if self.transform_type == 'mapping':
            if not self.transform_mapping:
                return value
                
            mapping = json.loads(self.transform_mapping)
            str_value = str(value)
            return mapping.get(str_value, value)
            
        if self.transform_type == 'function':
            if not self.transform_function:
                return value
                
            # Implémentation sécurisée de l'exécution de code - à améliorer
            local_dict = {'value': value, 'result': value}
            try:
                # pylint: disable=exec-used
                exec(self.transform_function, {'__builtins__': {}}, local_dict)
                return local_dict.get('result', value)
            except Exception as e:
                _logger.error("Erreur lors de l'exécution de la fonction de transformation: %s", str(e))
                return value
