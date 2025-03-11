# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class UdmDashboardMetric(models.Model):
    """Model for storing and managing UDM Pro dashboard metrics.
    
    This model stores real-time and near-real-time metrics from UDM Pro devices,
    such as bandwidth usage, CPU/memory utilization, connected clients count,
    and security threat counts. Each metric is associated with a specific site
    and includes both raw and formatted values for display.
    
    The model supports:
    - Multiple metric types with appropriate formatting
    - Status computation based on thresholds
    - Historical data storage for trending
    - Automatic value formatting based on metric type
    
    Metrics are ordered by last update time to show most recent data first.
    """
    _name = 'udm.dashboard.metric'
    _description = 'UDM Dashboard Metric'
    _order = 'last_update desc'  # Most recent metrics first
    
    # Site this metric belongs to, cascade deletion if site is deleted
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
    
    # Type of metric being tracked
    metric_type = fields.Selection([
        ('bandwidth_usage', 'Bandwidth Usage'),  # Network bandwidth utilization
        ('cpu_usage', 'CPU Usage'),  # CPU utilization percentage
        ('memory_usage', 'Memory Usage'),  # Memory utilization percentage
        ('clients_count', 'Connected Clients'),  # Number of connected network clients
        ('wan_status', 'WAN Status'),  # WAN connection status (up/down)
        ('threat_count', 'Security Threats'),  # Number of security threats detected
        ('device_status', 'Device Status'),  # Status of network devices (online/offline)
    ], string='Metric Type', required=True)
    
    # Raw metric values
    current_value = fields.Char(string='Current Value', required=True,
        help="Current raw value of the metric")
    max_value = fields.Char(string='Maximum Value',
        help="Maximum allowed value for this metric, used for threshold calculations")
    history_data = fields.Text(string='Historical Data',
        help="JSON data containing historical values for graphing")
    last_update = fields.Datetime(string='Last Update', default=fields.Datetime.now,
        help="Timestamp of the last metric update")
    
    # Computed fields for display
    formatted_value = fields.Char(compute='_compute_formatted_value', string='Formatted Value',
        help="Human-readable formatted value with appropriate units")
    status = fields.Selection([
        ('normal', 'Normal'),  # Operating within normal parameters
        ('warning', 'Warning'),  # Approaching critical thresholds
        ('critical', 'Critical'),  # Exceeded critical thresholds
    ], compute='_compute_status', string='Status',
        help="Status indicator based on metric thresholds")
    
    @api.depends('current_value', 'metric_type')
    def _compute_formatted_value(self):
        """Compute a human-readable formatted value based on the metric type.
        
        This method formats the raw value into a user-friendly string with appropriate units:
        - For bandwidth: Converts to Mbps or Gbps with 1 decimal place
        - For CPU/Memory: Adds percentage sign with 1 decimal place
        - For other metrics: Uses the raw value as is
        
        The formatted value is used in the UI to display metrics in a consistent
        and readable format.
        """
        for record in self:
            if not record.current_value:
                record.formatted_value = ''
                continue
                
            if record.metric_type == 'bandwidth_usage':
                try:
                    value = float(record.current_value)
                    if value >= 1000:
                        record.formatted_value = f"{value/1000:.1f} Gbps"
                    else:
                        record.formatted_value = f"{value:.1f} Mbps"
                except (ValueError, TypeError):
                    record.formatted_value = record.current_value
            elif record.metric_type in ['cpu_usage', 'memory_usage']:
                try:
                    value = float(record.current_value)
                    record.formatted_value = f"{value:.1f}%"
                except (ValueError, TypeError):
                    record.formatted_value = record.current_value
            else:
                record.formatted_value = record.current_value
    
    @api.depends('current_value', 'metric_type', 'max_value')
    def _compute_status(self):
        """Compute the status of the metric based on predefined thresholds.
        
        This method evaluates the current value against thresholds to determine
        if the metric is in a normal, warning, or critical state. The thresholds
        vary by metric type:
        
        CPU/Memory Usage:
        - Critical: >= 90%
        - Warning: >= 75%
        
        Bandwidth Usage:
        - Critical: >= 90% of max
        - Warning: >= 75% of max
        
        Security Threats:
        - Critical: >= 10 threats
        - Warning: >= 5 threats
        
        WAN Status:
        - Critical: not 'up'
        
        Device Status (format: 'online/total'):
        - Critical: > 2 devices offline
        - Warning: > 0 devices offline
        
        The status is used in the UI to highlight metrics that need attention,
        using color-coded badges (green/yellow/red).
        """
        for record in self:
            status = 'normal'
            
            try:
                if record.metric_type in ['cpu_usage', 'memory_usage']:
                    value = float(record.current_value)
                    if value >= 90:
                        status = 'critical'
                    elif value >= 75:
                        status = 'warning'
                elif record.metric_type == 'bandwidth_usage':
                    if record.max_value:
                        value = float(record.current_value)
                        max_val = float(record.max_value)
                        usage_pct = (value / max_val) * 100
                        if usage_pct >= 90:
                            status = 'critical'
                        elif usage_pct >= 75:
                            status = 'warning'
                elif record.metric_type == 'threat_count':
                    value = int(record.current_value)
                    if value >= 10:
                        status = 'critical'
                    elif value >= 5:
                        status = 'warning'
                elif record.metric_type == 'wan_status':
                    if record.current_value != 'up':
                        status = 'critical'
                elif record.metric_type == 'device_status':
                    if '/' in record.current_value:
                        online, total = map(int, record.current_value.split('/'))
                        offline = total - online
                        if offline > 2:
                            status = 'critical'
                        elif offline > 0:
                            status = 'warning'
            except (ValueError, TypeError):
                # If we can't parse the value, assume normal status
                status = 'normal'
            
            record.status = status

class UdmDashboardStat(models.Model):
    """Model for storing and analyzing historical UDM Pro statistics.
    
    This model stores historical statistical data from UDM Pro devices for
    long-term trend analysis and reporting. It supports both raw data points
    and aggregated statistics (e.g., daily averages, totals).
    
    Key features:
    - Multiple statistic types (bandwidth, clients, threats, uptime)
    - Support for different units of measurement
    - Time-based statistics with start/end times
    - Aggregation capabilities (sum, average, min, max)
    - Built-in graphing support
    
    Statistics are ordered by date (descending) to show most recent data first.
    Raw and aggregated statistics are stored separately to maintain data
    integrity while allowing flexible reporting.
    """
    _name = 'udm.dashboard.stat'
    _description = 'UDM Dashboard Statistic'
    _order = 'date desc'  # Most recent statistics first
    
    # Site this statistic belongs to, cascade deletion if site is deleted
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
    
    # Date of the statistic record
    date = fields.Date(string='Date', required=True, default=fields.Date.today,
        help="Date this statistic was recorded")
    
    # Type of statistic being tracked
    stat_type = fields.Selection([
        ('bandwidth_usage', 'Bandwidth Usage'),  # Total bandwidth used
        ('client_count', 'Client Count'),  # Number of clients over time
        ('threat_blocked', 'Threats Blocked'),  # Number of security threats blocked
        ('device_uptime', 'Device Uptime'),  # Device uptime duration
    ], string='Statistic Type', required=True,
        help="Type of statistical data being recorded")
    
    # Numerical value and its unit
    value = fields.Float(string='Value', required=True,
        help="Numerical value of the statistic")
    unit = fields.Selection([
        ('bytes', 'Bytes'),  # For bandwidth measurements
        ('count', 'Count'),  # For counting items (clients, threats)
        ('percentage', 'Percentage'),  # For utilization metrics
        ('hours', 'Hours'),  # For time-based metrics
    ], string='Unit', required=True,
        help="Unit of measurement for the value")
    
    # Time range for detailed statistics
    time_start = fields.Datetime(string='Start Time',
        help="Start time for time-based statistics (e.g. hourly bandwidth usage)")
    time_end = fields.Datetime(string='End Time',
        help="End time for time-based statistics")
    
    # Aggregation fields
    is_aggregate = fields.Boolean(string='Is Aggregate', default=False,
        help="Indicates if this record represents aggregated data")
    aggregate_type = fields.Selection([
        ('sum', 'Sum'),  # Total over the period
        ('avg', 'Average'),  # Average over the period
        ('min', 'Minimum'),  # Minimum value in the period
        ('max', 'Maximum'),  # Maximum value in the period
    ], string='Aggregate Type',
        help="Type of aggregation used for this record")
    
    @api.model
    def aggregate_stats(self, site_id, stat_type, start_date, end_date, aggregate_type='avg'):
        """Aggregate statistics for a specific site and type over a date range.
        
        This method calculates aggregate values (sum, average, min, max) for
        non-aggregated statistics within the specified date range.
        
        Args:
            site_id (int): ID of the site to aggregate stats for
            stat_type (str): Type of statistic to aggregate
            start_date (date): Start date of the range (inclusive)
            end_date (date): End date of the range (inclusive)
            aggregate_type (str): Type of aggregation to perform
                'sum': Total of all values
                'avg': Average of all values
                'min': Minimum value
                'max': Maximum value
        
        Returns:
            float: The aggregated value, or 0.0 if no stats found
        """
        domain = [
            ('site_id', '=', site_id),
            ('stat_type', '=', stat_type),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('is_aggregate', '=', False)  # Only aggregate raw statistics
        ]
        
        stats = self.search(domain)
        if not stats:
            return 0.0
            
        values = stats.mapped('value')
        
        if aggregate_type == 'sum':
            return sum(values)
        elif aggregate_type == 'avg':
            return sum(values) / len(values)
        elif aggregate_type == 'min':
            return min(values)
        elif aggregate_type == 'max':
            return max(values)
        else:
            return 0.0
            
    def action_view_graph(self):
        """Open a graph view showing statistics over time.
        
        This method creates an action to display a line graph of the statistic
        values over time. The graph shows raw (non-aggregated) values grouped
        by day.
        
        The graph view is configured to:
        - Show values on the y-axis
        - Use a line graph for trend visualization
        - Group data points by day on the x-axis
        - Filter for the same site and statistic type
        - Exclude aggregated records
        
        Returns:
            dict: An action dictionary that Odoo uses to open the graph view
        """
        self.ensure_one()
        action = {
            'name': _('Statistics Graph'),
            'view_mode': 'graph',
            'res_model': 'udm.dashboard.stat',
            'type': 'ir.actions.act_window',
            'domain': [
                ('site_id', '=', self.site_id.id),
                ('stat_type', '=', self.stat_type),
                ('is_aggregate', '=', False)  # Show only raw values
            ],
            'context': {
                'graph_measure': 'value',  # Y-axis measurement
                'graph_mode': 'line',  # Line graph for trends
                'graph_groupbys': ['date:day']  # Group by day on X-axis
            }
        }
        return action
