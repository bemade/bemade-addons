# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
# pylint: enable=import-error

import logging

_logger = logging.getLogger(__name__)

class UnifiDashboardMetric(models.Model):
    """Métriques en temps réel pour le tableau de bord UniFi
    
    Ce modèle stocke les métriques en temps réel pour les sites UniFi, comme
    l'utilisation de la bande passante, le nombre de clients connectés, etc.
    """
    _name = 'unifi.dashboard.metric'
    _description = 'UniFi Dashboard Real-time Metric'
    _order = 'create_date desc'
    
    name = fields.Char(
        string='Name',
        required=True,
        help='Name of the metric'
    )
    
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='The site this metric belongs to'
    )
    
    metric_type = fields.Selection(
        selection=[
            ('bandwidth', 'Bandwidth Usage'),
            ('clients', 'Connected Clients'),
            ('cpu', 'CPU Usage'),
            ('memory', 'Memory Usage'),
            ('storage', 'Storage Usage'),
            ('latency', 'Network Latency'),
            ('errors', 'Network Errors'),
            ('other', 'Other')
        ],
        string='Metric Type',
        required=True,
        help='Type of metric being tracked'
    )
    
    value = fields.Float(
        string='Value',
        help='Current value of the metric'
    )
    
    unit = fields.Selection(
        selection=[
            ('bps', 'Bits per second'),
            ('Kbps', 'Kilobits per second'),
            ('Mbps', 'Megabits per second'),
            ('Gbps', 'Gigabits per second'),
            ('count', 'Count'),
            ('percent', 'Percentage'),
            ('ms', 'Milliseconds'),
            ('B', 'Bytes'),
            ('KB', 'Kilobytes'),
            ('MB', 'Megabytes'),
            ('GB', 'Gigabytes'),
            ('other', 'Other')
        ],
        string='Unit',
        required=True,
        help='Unit of measurement for the metric'
    )
    
    timestamp = fields.Datetime(
        string='Timestamp',
        required=True,
        default=fields.Datetime.now,
        help='Time when this metric was recorded'
    )
    
    device_id = fields.Many2one(
        comodel_name='unifi.device',
        string='Device',
        ondelete='set null',
        help='The device this metric is associated with, if applicable'
    )
    
    network_id = fields.Many2one(
        comodel_name='unifi.network',
        string='Network',
        ondelete='set null',
        help='The network this metric is associated with, if applicable'
    )
    
    is_critical = fields.Boolean(
        string='Critical',
        default=False,
        help='Whether this metric indicates a critical condition'
    )
    
    threshold = fields.Float(
        string='Threshold',
        help='Threshold value for triggering alerts'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this metric'
    )
    
    # Les méthodes create et write ont été supprimées car elles n'implémentaient pas de logique spécifique
    
    def update_metric(self, value, timestamp=None):
        """Update the value of this metric
        
        Args:
            value: New value for the metric
            timestamp: Optional timestamp for the update
            
        Returns:
            Boolean indicating success
        """
        self.ensure_one()
        
        vals = {
            'value': value,
            'timestamp': timestamp or fields.Datetime.now()
        }
        
        # Check if the value exceeds the threshold
        if self.threshold and value > self.threshold:
            vals['is_critical'] = True
            
            # Log a warning for critical metrics
            _logger.warning(
                'Critical metric detected for site %s: %s = %s %s (threshold: %s)',
                self.site_id.name, self.name, value, self.unit, self.threshold
            )
        else:
            vals['is_critical'] = False
        
        return self.write(vals)
