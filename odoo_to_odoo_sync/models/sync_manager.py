# Copyright 2025 Codeium
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Synchronization Management System.

This module implements the core synchronization logic and conflict resolution
strategies. It manages the overall synchronization process, including queuing
operations, handling retries, and ensuring data consistency across instances.
"""

import json
import logging
from datetime import datetime, timedelta
import xmlrpc.client

from odoo import fields, models

_logger = logging.getLogger(__name__)

class SyncConflictException(Exception):
    """Exception raised when a synchronization conflict is detected.
    
    This exception is raised when the synchronization process encounters
    conflicting changes between source and destination instances that
    cannot be automatically resolved based on the current conflict
    resolution strategy.
    """
    pass

class OdooSyncManager(models.Model):
    """Manages synchronization operations between Odoo instances.

    This class is responsible for orchestrating the synchronization process,
    including:
    - Managing synchronization queues
    - Handling conflict resolution
    - Coordinating data transfer between instances
    - Monitoring synchronization status
    - Implementing retry mechanisms
    - Logging synchronization events

    The synchronization process is configurable through various strategies
    and can be customized based on specific business needs.
    """
    _name = 'odoo.sync.manager'
    _description = 'Odoo Sync Manager'

    conflict_strategy = fields.Selection(
        selection=[
            ('timestamp', 'Last Modified'),
            ('manual', 'Manual Resolution'),
            ('source_priority', 'Source Priority'),
            ('destination_priority', 'Destination Priority')
        ],
        default='timestamp', 
        required=True
    )

    def _get_sync_models(self):
        """Récupère tous les modèles actifs à synchroniser"""
        return self.env['odoo.sync.model'].search([('active', '=', True)])

    def _queue_sync(self, record, operation, changed_fields=None):
        """Ajoute une opération dans la queue de synchronisation"""
        sync_model = self.env['odoo.sync.model'].search([
            ('model_id.model', '=', record._name),
            ('active', '=', True)
        ])
        if not sync_model:
            return

        # Préparation des données à synchroniser
        data = record.read()[0] if operation != 'unlink' else {'id': record.id}
        
        # Pour chaque destination configurée
        for destination in sync_model.destination_ids.filtered('active'):
            # Vérifier si les champs modifiés sont à synchroniser
            if operation == 'write' and changed_fields:
                sync_fields = destination.field_ids.mapped('name')
                if not any(field in sync_fields for field in changed_fields):
                    continue

            # Création de l'entrée dans la file
            self.env['odoo.sync.queue'].create({
                'model_id': sync_model.id,
                'record_id': record.id,
                'operation': operation,
                'state': 'pending',
                'priority': sync_model.priority,
                'data': json.dumps(data)
            })

    def _process_sync_queue(self):
        """Traitement de la file d'attente"""
        queue_items = self.env['odoo.sync.queue'].search([
            ('state', '=', 'pending'),
            '|',
            ('next_retry', '<=', fields.Datetime.now()),
            ('next_retry', '=', False)
        ], order='priority desc, retry_count, create_date')

        for item in queue_items:
            try:
                item.state = 'processing'
                self._process_queue_item(item)
                item.state = 'done'
            except Exception as e:
                _logger.error(f'Erreur lors du traitement de {item.name}: {str(e)}')
                item.write({
                    'state': 'error',
                    'error_message': str(e),
                    'retry_count': item.retry_count + 1
                })
                if item.retry_count < item.max_retries:
                    delay = 2 ** item.retry_count  # Délai exponentiel
                    item.next_retry = fields.Datetime.now() + timedelta(minutes=delay)
                self.env['odoo.sync.log'].create({
                    'queue_id': item.id,
                    'state': 'error',
                    'message': str(e)
                })

    def _process_queue_item(self, item):
        """Traite un élément de la file d'attente"""
        model = item.model_id
        data = json.loads(item.data)
        
        for destination in model.destination_ids.filtered('active'):
            instance = destination.instance_id
            models, uid = instance.get_connection()
            
            try:
                if item.operation == 'create':
                    result = models.execute_kw(
                        instance.database, uid, instance.password,
                        destination.target_model, 'create',
                        [self._prepare_sync_data(data, destination)]
                    )
                elif item.operation == 'write':
                    result = models.execute_kw(
                        instance.database, uid, instance.password,
                        destination.target_model, 'write',
                        [[data['id']], self._prepare_sync_data(data, destination)]
                    )
                elif item.operation == 'unlink':
                    result = models.execute_kw(
                        instance.database, uid, instance.password,
                        destination.target_model, 'unlink',
                        [[data['id']]]
                    )
                
                self.env['odoo.sync.log'].create({
                    'queue_id': item.id,
                    'state': 'success',
                    'message': f'Synchronisation réussie vers {instance.name}'
                })
            
            except xmlrpc.client.Fault as e:
                raise Exception(f'Erreur RPC vers {instance.name}: {str(e)}')

    def _prepare_sync_data(self, data, destination):
        """Prépare les données pour la synchronisation"""
        sync_fields = destination.field_ids
        result = {}
        
        for field in sync_fields:
            if field.name in data:
                value = data[field.name]
                if not value and field.sync_default:
                    value = field.sync_default
                result[field.name] = value
        
        return result

    def _handle_conflict(self, local_data, remote_data):
        """Gestion des conflits selon la stratégie configurée"""
        strategy = self.conflict_strategy
        _logger.info(f'Résolution de conflit avec stratégie: {strategy}')

        if strategy == 'timestamp':
            return self._resolve_by_timestamp(local_data, remote_data)
        elif strategy == 'manual':
            return self._flag_for_manual_resolution(local_data, remote_data)
        elif strategy == 'source_priority':
            return local_data
        elif strategy == 'destination_priority':
            return remote_data

    def _resolve_by_timestamp(self, local, remote):
        """Résout un conflit en utilisant l'horodatage"""
        local_date = fields.Datetime.from_string(local['write_date'])
        remote_date = fields.Datetime.from_string(remote['write_date'])
        return local if local_date > remote_date else remote

    def _flag_for_manual_resolution(self, local, remote):
        """Marque un conflit pour résolution manuelle"""
        self.env['odoo.sync.conflict'].create({
            'local_data': json.dumps(local),
            'remote_data': json.dumps(remote),
            'model_name': local['model'],
            'record_id': local['id'],
            'state': 'pending'
        })
        raise SyncConflictException('Conflit nécessitant une résolution manuelle')
