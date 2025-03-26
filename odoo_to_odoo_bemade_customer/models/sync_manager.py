# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Gestionnaire de synchronisation pour Odoo to Bemade Customer.

Ce module coordonne les processus de synchronisation entre Odoo client et Bemade.
"""

import time
import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OdooToBemadeCustomerSyncManager(models.AbstractModel):
    """Gestionnaire de synchronisation.

    Coordonne les processus de synchronisation entre Odoo client et Bemade.
    """

    _name = 'odoo.to.bemade.customer.sync.manager'
    _description = 'Gestionnaire de synchronisation Bemade'
    _inherit = 'odoo.sync.manager'

    @api.model
    def sync_all(self):
        """Synchronise tous les modèles actifs avec Bemade.

        Lance le processus de synchronisation pour tous les modèles configurés
        par ordre de priorité, et traite ensuite la file d'attente.
        """
        config = self.env['odoo.to.bemade.customer.config'].get_config()
        if not config:
            raise UserError(_("Aucune configuration Bemade active trouvée"))

        if config.state != 'connected':
            raise UserError(_("La configuration Bemade n'est pas connectée"))

        # Récupérer tous les modèles actifs
        models = self.env['odoo.to.bemade.customer.sync.model'].search(
            [('active', '=', True), ('config_id', '=', config.id)],
            order='priority desc, id'
        )

        log_vals = {
            'operation': 'sync',
            'direction': 'to_bemade',
            'result': 'success',
            'details': _("Démarrage de la synchronisation complète")
        }
        self.env['odoo.to.bemade.customer.sync.log'].log(**log_vals)

        # Synchroniser chaque modèle
        for model in models:
            try:
                model.action_sync_model()
            except Exception as e:
                _logger.error(f"Erreur lors de la synchronisation du modèle {model.name}: {str(e)}")
                log_vals = {
                    'operation': 'error',
                    'model': model,
                    'result': 'error',
                    'details': str(e)
                }
                self.env['odoo.to.bemade.customer.sync.log'].log(**log_vals)

        # Traitement de la file d'attente
        self.process_queue()

        # Mise à jour de la date de dernière synchronisation
        config.write({'last_sync': fields.Datetime.now()})

        return True

    @api.model
    def process_queue(self, limit=50, queue_ids=None):
        """Traite les éléments en attente dans la file d'attente.

        Args:
            limit: Nombre maximum d'éléments à traiter
            queue_ids: Liste d'IDs spécifiques à traiter, sinon tous les éléments en attente
        """
        domain = [('state', '=', 'pending')]
        
        # Si next_retry est défini, vérifier qu'il est passé
        domain += [
            '|',
            ('next_retry', '=', False),
            ('next_retry', '<=', fields.Datetime.now())
        ]
        
        if queue_ids:
            domain += [('id', 'in', queue_ids if isinstance(queue_ids, list) else [queue_ids])]
            
        queue_items = self.env['odoo.to.bemade.customer.sync.queue'].search(
            domain, order='priority desc, create_date', limit=limit
        )
        
        for queue_item in queue_items:
            self._process_queue_item(queue_item)
            
        return True
    
    def _process_queue_item(self, queue_item):
        """Traite un élément spécifique de la file d'attente."""
        start_time = time.time()
        config = self.env['odoo.to.bemade.customer.config'].get_config()
        
        if not config:
            queue_item.write({
                'state': 'error',
                'error_message': _("Aucune configuration Bemade active trouvée")
            })
            return False
            
        if config.state != 'connected':
            queue_item.write({
                'state': 'error',
                'error_message': _("La configuration Bemade n'est pas connectée")
            })
            return False
            
        # Marquer comme en cours de traitement
        queue_item.write({'state': 'processing'})
        
        try:
            # Récupérer les informations de modèle et d'enregistrement
            model_sync = queue_item.model_id
            model_obj = self.env[model_sync.model]
            record = model_obj.browse(queue_item.record_id)
            
            if not record.exists():
                queue_item.write({
                    'state': 'error',
                    'error_message': _("L'enregistrement n'existe plus"),
                    'execution_time': time.time() - start_time
                })
                return False
                
            # Établir la connexion avec Bemade
            conn = config.get_connection()
            
            # Effectuer l'opération selon le type
            result = False
            if queue_item.operation == 'sync':
                # Synchronisation de l'enregistrement vers Bemade
                result = self._sync_record_to_bemade(conn, model_sync, record)
            elif queue_item.operation == 'delete':
                # Suppression de l'enregistrement chez Bemade
                result = self._delete_record_from_bemade(conn, model_sync, record)
                
            # Si tout s'est bien passé
            if result:
                queue_item.write({
                    'state': 'done',
                    'result': str(result),
                    'execution_time': time.time() - start_time
                })
                
                # Journalisation du succès
                log_vals = {
                    'operation': queue_item.operation,
                    'model': model_sync.model,
                    'record_id': record.id,
                    'direction': 'to_bemade',
                    'result': 'success',
                    'queue_id': queue_item.id,
                    'execution_time': time.time() - start_time,
                    'details': str(result) if result else ""
                }
                self.env['odoo.to.bemade.customer.sync.log'].log(**log_vals)
                
                return True
            else:
                # Échec sans exception
                queue_item.write({
                    'state': 'error',
                    'error_message': _("Échec de l'opération - aucun résultat"),
                    'execution_time': time.time() - start_time
                })
                
                # Journalisation de l'erreur
                log_vals = {
                    'operation': queue_item.operation,
                    'model': model_sync.model,
                    'record_id': record.id,
                    'direction': 'to_bemade',
                    'result': 'error',
                    'queue_id': queue_item.id,
                    'execution_time': time.time() - start_time,
                    'details': _("Échec de l'opération - aucun résultat")
                }
                self.env['odoo.to.bemade.customer.sync.log'].log(**log_vals)
                
                return False
                
        except Exception as e:
            # Gestion des tentatives
            retry_count = queue_item.retry_count + 1
            error_message = f"{str(e)}"
            
            if retry_count < queue_item.max_retries:
                # Calculer le délai avant la prochaine tentative (croissance exponentielle)
                delay = 5 * (2 ** (retry_count - 1))  # 5, 10, 20, 40, ...
                next_retry = fields.Datetime.now() + timedelta(minutes=delay)
                
                queue_item.write({
                    'state': 'pending',
                    'retry_count': retry_count,
                    'error_message': error_message,
                    'next_retry': next_retry,
                    'execution_time': time.time() - start_time
                })
            else:
                # Nombre maximum de tentatives atteint
                queue_item.write({
                    'state': 'error',
                    'retry_count': retry_count,
                    'error_message': error_message,
                    'execution_time': time.time() - start_time
                })
                
            # Journalisation de l'erreur
            log_vals = {
                'operation': queue_item.operation,
                'model': queue_item.model_id.model,
                'record_id': queue_item.record_id,
                'direction': 'to_bemade',
                'result': 'error',
                'queue_id': queue_item.id,
                'execution_time': time.time() - start_time,
                'details': error_message
            }
            self.env['odoo.to.bemade.customer.sync.log'].log(**log_vals)
            
            _logger.error(f"Erreur lors du traitement de la file d'attente: {error_message}")
            return False
            
    def _sync_record_to_bemade(self, connection, model_sync, record):
        """Synchronise un enregistrement vers Bemade.
        
        Cette méthode est destinée à être étendue ou remplacée par 
        une implémentation spécifique selon les besoins.
        """
        # Mapping des champs
        mapping = {}
        if model_sync.field_mapping:
            try:
                mapping = eval(model_sync.field_mapping)
            except Exception as e:
                _logger.error(f"Erreur lors de l'évaluation du mapping: {str(e)}")
                mapping = {}
                
        # Préparer les données à envoyer
        data = {}
        for local_field, remote_field in mapping.items():
            if hasattr(record, local_field):
                data[remote_field] = record[local_field]
                
        # Appel à l'API Bemade
        # Cette partie doit être implémentée selon l'API spécifique de Bemade
        
        # Simulation pour le moment
        _logger.info(f"Simulation de synchronisation vers Bemade: {data}")
        return {'remote_id': f'bem-{record.id}', 'status': 'success'}
        
    def _delete_record_from_bemade(self, connection, model_sync, record):
        """Supprime un enregistrement chez Bemade.
        
        Cette méthode est destinée à être étendue ou remplacée par
        une implémentation spécifique selon les besoins.
        """
        # Appel à l'API Bemade pour supprimer l'enregistrement
        # Cette partie doit être implémentée selon l'API spécifique de Bemade
        
        # Simulation pour le moment
        _logger.info(f"Simulation de suppression chez Bemade: {record}")
        return {'status': 'deleted'}
