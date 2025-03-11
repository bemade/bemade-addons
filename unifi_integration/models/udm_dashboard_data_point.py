# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmDashboardDataPoint(models.Model):
    """Data point for dashboard statistics"""
    _name = 'udm.dashboard.data.point'
    _description = 'Dashboard Data Point'
    _order = 'sequence'
    
    # Reference to the statistic this data point belongs to
    stat_id = fields.Many2one('udm.dashboard.stat', string='Statistic',
                             required=True, ondelete='cascade')
    
    # Data point attributes
    sequence = fields.Integer(string='Sequence', default=10,
                            help='Order of this data point in the series')
    value = fields.Float(string='Value',
                        help='Numeric value of this data point')
    timestamp = fields.Datetime(string='Timestamp',
                              help='When this data point was recorded')
