# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
# pylint: enable=import-error

import logging
import json
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class UnifiDashboardStat(models.Model):
    """Statistiques historiques pour le tableau de bord UniFi
    
    Ce modèle stocke les statistiques historiques pour les sites UniFi, permettant
    de suivre l'évolution des métriques dans le temps et de générer des rapports.
    """
    _name = 'unifi.dashboard.stat'
    _description = 'UniFi Dashboard Historical Statistic'
    _order = 'date desc, name'
    
    name = fields.Char(
        string='Name',
        required=True,
        help='Name of the statistic'
    )
    
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='The site this statistic belongs to'
    )
    
    stat_type = fields.Selection(
        selection=[
            ('bandwidth_usage', 'Bandwidth Usage'),
            ('client_count', 'Client Count'),
            ('traffic_volume', 'Traffic Volume'),
            ('device_uptime', 'Device Uptime'),
            ('error_rate', 'Error Rate'),
            ('latency', 'Network Latency'),
            ('signal_strength', 'Signal Strength'),
            ('other', 'Other')
        ],
        string='Statistic Type',
        required=True,
        help='Type of statistic being tracked'
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        help='Date this statistic was recorded for'
    )
    
    period = fields.Selection(
        selection=[
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly')
        ],
        string='Period',
        required=True,
        default='daily',
        help='Time period this statistic covers'
    )
    
    value_min = fields.Float(
        string='Minimum Value',
        help='Minimum value recorded during the period'
    )
    
    value_max = fields.Float(
        string='Maximum Value',
        help='Maximum value recorded during the period'
    )
    
    value_avg = fields.Float(
        string='Average Value',
        help='Average value over the period'
    )
    
    value_total = fields.Float(
        string='Total Value',
        help='Total cumulative value over the period'
    )
    
    unit = fields.Selection(
        selection=[
            ('bps', 'Bits per second'),
            ('Kbps', 'Kilobits per second'),
            ('Mbps', 'Megabits per second'),
            ('Gbps', 'Gigabits per second'),
            ('B', 'Bytes'),
            ('KB', 'Kilobytes'),
            ('MB', 'Megabytes'),
            ('GB', 'Gigabytes'),
            ('TB', 'Terabytes'),
            ('count', 'Count'),
            ('percent', 'Percentage'),
            ('ms', 'Milliseconds'),
            ('other', 'Other')
        ],
        string='Unit',
        required=True,
        help='Unit of measurement for the statistic'
    )
    
    device_id = fields.Many2one(
        comodel_name='unifi.device',
        string='Device',
        ondelete='set null',
        help='The device this statistic is associated with, if applicable'
    )
    
    network_id = fields.Many2one(
        comodel_name='unifi.network',
        string='Network',
        ondelete='set null',
        help='The network this statistic is associated with, if applicable'
    )
    
    data_points = fields.Text(
        string='Data Points',
        help='JSON-encoded array of data points for this statistic'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this statistic'
    )
    
    # Les méthodes create et write ont été supprimées car elles n'implémentaient pas de logique spécifique
    
    def get_data_points(self):
        """Get the data points for this statistic as a Python object
        
        Returns:
            List of data points or empty list if none
        """
        self.ensure_one()
        
        if not self.data_points:
            return []
        
        try:
            return json.loads(self.data_points)
        except json.JSONDecodeError:
            _logger.error('Failed to decode data points for statistic %s', self.name)
            return []
    
    def set_data_points(self, data_points):
        """Set the data points for this statistic
        
        Args:
            data_points: List of data points to store
            
        Returns:
            Boolean indicating success
        """
        self.ensure_one()
        
        try:
            self.data_points = json.dumps(data_points)
            return True
        except Exception as e:
            _logger.error('Failed to encode data points for statistic %s: %s', self.name, str(e))
            return False
    
    def add_data_point(self, value, timestamp=None):
        """Add a new data point to this statistic
        
        Args:
            value: Value to add
            timestamp: Optional timestamp for the data point
            
        Returns:
            Boolean indicating success
        """
        self.ensure_one()
        
        # Get existing data points
        data_points = self.get_data_points()
        
        # Create new data point
        new_point = {
            'value': value,
            'timestamp': timestamp or fields.Datetime.now().isoformat()
        }
        
        # Add to list
        data_points.append(new_point)
        
        # Update min/max/avg values
        values = [p['value'] for p in data_points]
        self.value_min = min(values)
        self.value_max = max(values)
        self.value_avg = sum(values) / len(values)
        
        # For cumulative stats like traffic volume, update the total
        if self.stat_type in ['traffic_volume']:
            self.value_total = sum(values)
        
        # Save updated data points
        return self.set_data_points(data_points)
    
    @api.model
    def generate_daily_stats(self, site_id, date=None):
        """Generate daily statistics from hourly metrics
        
        Args:
            site_id: ID of the site to generate statistics for
            date: Optional date to generate statistics for (defaults to yesterday)
            
        Returns:
            List of created statistic records
        """
        if not date:
            date = fields.Date.today() - timedelta(days=1)
            
        # Get all hourly stats for the given site and date
        hourly_stats = self.search([
            ('site_id', '=', site_id),
            ('date', '=', date),
            ('period', '=', 'hourly')
        ])
        
        # Group by stat_type
        stats_by_type = {}
        for stat in hourly_stats:
            if stat.stat_type not in stats_by_type:
                stats_by_type[stat.stat_type] = []
            stats_by_type[stat.stat_type].append(stat)
        
        # Create daily stats for each type
        created_stats = []
        for stat_type, stats in stats_by_type.items():
            if not stats:
                continue
                
            # Get a representative stat to copy metadata from
            sample_stat = stats[0]
            
            # Calculate aggregated values
            values = [stat.value_avg for stat in stats if stat.value_avg]
            if not values:
                continue
                
            # Create daily stat
            daily_stat = self.create({
                'name': f"Daily {sample_stat.name}",
                'site_id': site_id,
                'stat_type': stat_type,
                'date': date,
                'period': 'daily',
                'value_min': min([stat.value_min for stat in stats if stat.value_min is not False]),
                'value_max': max([stat.value_max for stat in stats if stat.value_max is not False]),
                'value_avg': sum(values) / len(values),
                'value_total': sum([stat.value_total for stat in stats if stat.value_total is not False]) if stat_type in ['traffic_volume'] else 0,
                'unit': sample_stat.unit,
                'device_id': sample_stat.device_id.id if sample_stat.device_id else False,
                'network_id': sample_stat.network_id.id if sample_stat.network_id else False,
                'notes': f"Aggregated from {len(stats)} hourly statistics"
            })
            
            created_stats.append(daily_stat)
            
        return created_stats
