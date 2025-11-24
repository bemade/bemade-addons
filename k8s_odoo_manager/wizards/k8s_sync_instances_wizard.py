import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class K8sSyncInstancesWizard(models.TransientModel):
    _name = 'k8s.sync.instances.wizard'
    _description = 'Sync Odoo Instances from Kubernetes'

    cluster_ids = fields.Many2many(
        'k8s.cluster',
        string='Clusters to Sync',
        default=lambda self: self._default_cluster_ids()
    )
    
    sync_all = fields.Boolean(
        string='Sync All Active Clusters',
        default=True,
        help='If checked, will sync all active clusters regardless of selection above'
    )
    
    sync_result = fields.Text(
        string='Sync Result',
        readonly=True
    )
    
    state = fields.Selection([
        ('draft', 'Ready to Sync'),
        ('syncing', 'Syncing...'),
        ('done', 'Sync Complete'),
    ], default='draft')

    @api.model
    def _default_cluster_ids(self):
        """Default to active clusters"""
        active_ids = self.env.context.get('active_ids', [])
        if active_ids and self.env.context.get('active_model') == 'k8s.cluster':
            return [(6, 0, active_ids)]
        else:
            # Return all active clusters
            clusters = self.env['k8s.cluster'].search([('active', '=', True)])
            return [(6, 0, clusters.ids)]

    def action_sync_instances(self):
        """Sync instances from selected clusters"""
        self.ensure_one()
        
        self.state = 'syncing'
        
        # Determine which clusters to sync
        if self.sync_all:
            clusters = self.env['k8s.cluster'].search([('active', '=', True)])
        else:
            clusters = self.cluster_ids.filtered('active')
        
        if not clusters:
            raise UserError(_('No active clusters selected for synchronization'))
        
        results = []
        total_synced = 0
        errors = []
        
        for cluster in clusters:
            try:
                _logger.info(f"Syncing instances from cluster: {cluster.name}")
                
                # Count instances before sync
                before_count = len(cluster.instance_ids)
                
                # Perform sync
                result = cluster.sync_odoo_instances()
                
                # Count instances after sync
                after_count = len(cluster.instance_ids)
                synced_count = after_count  # This is the total count, not delta
                
                results.append(f"✓ {cluster.name}: {synced_count} instances")
                total_synced += synced_count
                
            except Exception as e:
                error_msg = f"✗ {cluster.name}: {str(e)}"
                results.append(error_msg)
                errors.append(error_msg)
                _logger.error(f"Sync failed for cluster {cluster.name}: {e}")
        
        # Prepare result message
        if errors:
            self.sync_result = f"Sync completed with errors:\n\n" + "\n".join(results)
            if len(errors) == len(clusters):
                self.sync_result += f"\n\n⚠️ All clusters failed to sync!"
            else:
                self.sync_result += f"\n\n✓ Total instances synced: {total_synced}"
        else:
            self.sync_result = f"✓ Sync completed successfully!\n\n" + "\n".join(results)
            self.sync_result += f"\n\n✓ Total instances synced: {total_synced}"
        
        self.state = 'done'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'k8s.sync.instances.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_close(self):
        """Close the wizard"""
        return {'type': 'ir.actions.act_window_close'}

    def action_view_instances(self):
        """View the synced instances"""
        self.ensure_one()
        
        if self.sync_all:
            clusters = self.env['k8s.cluster'].search([('active', '=', True)])
        else:
            clusters = self.cluster_ids.filtered('active')
        
        domain = [('cluster_id', 'in', clusters.ids)]
        
        return {
            'name': _('Synced Odoo Instances'),
            'type': 'ir.actions.act_window',
            'res_model': 'k8s.odoo.instance',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'search_default_group_cluster': 1},
        }
