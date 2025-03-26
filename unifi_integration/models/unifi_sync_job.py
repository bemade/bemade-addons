# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
# pylint: enable=import-error

import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class UnifiSyncJob(models.Model):
    """Manages synchronization jobs for UniFi sites
    
    This model tracks synchronization jobs, including their status, duration,
    and any errors that occurred during synchronization.
    """
    _name = 'unifi.sync.job'
    _description = 'UniFi Synchronization Job'
    _order = 'start_time desc'
    
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='The site this synchronization job is for'
    )
    
    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        help='Name of the synchronization job'
    )
    
    sync_type = fields.Selection(
        selection=[
            ('manual', 'Manual'),
            ('scheduled', 'Scheduled'),
            ('automatic', 'Automatic')
        ],
        string='Sync Type',
        required=True,
        default='manual',
        help='Type of synchronization'
    )
    
    api_type = fields.Selection(
        selection=[
            ('site_manager', 'Site Manager API'),
            ('controller', 'Controller API')
        ],
        string='API Type',
        required=True,
        help='Type of API used for this synchronization job'
    )
    
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled')
        ],
        string='State',
        required=True,
        default='pending',
        help='Current state of the synchronization job'
    )
    
    status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
            ('success', 'Success'),
            ('warning', 'Warning'),
            ('error', 'Error'),
            ('info', 'Information')
        ],
        string='Status',
        help='Status of the synchronization job'
    )
    
    start_time = fields.Datetime(
        string='Start Time',
        default=fields.Datetime.now,
        help='Date and time when this job started'
    )
    
    end_time = fields.Datetime(
        string='End Time',
        help='Date and time when this job ended'
    )
    
    duration = fields.Float(
        string='Duration (seconds)',
        compute='_compute_duration',
        store=True,
        help='Duration of the synchronization job in seconds'
    )
    
    error_message = fields.Text(
        string='Error Message',
        help='Error message if the job failed'
    )
    
    message = fields.Text(
        string='Message',
        help='Detailed message about the synchronization job'
    )
    
    log_ids = fields.One2many(
        comodel_name='unifi.api.log',
        inverse_name='sync_job_id',
        string='API Logs',
        help='API calls made during this synchronization job'
    )
    
    api_call_count = fields.Integer(
        string='API Call Count',
        compute='_compute_api_call_count',
        store=True,
        help='Number of API calls made during this job'
    )
    
    success_rate = fields.Float(
        string='Success Rate (%)',
        compute='_compute_success_rate',
        store=True,
        help='Percentage of successful API calls'
    )
    
    created_records = fields.Integer(
        string='Created Records',
        default=0,
        help='Number of records created during this job'
    )
    
    updated_records = fields.Integer(
        string='Updated Records',
        default=0,
        help='Number of records updated during this job'
    )
    
    deleted_records = fields.Integer(
        string='Deleted Records',
        default=0,
        help='Number of records deleted during this job'
    )
    
    @api.depends('site_id', 'start_time', 'sync_type')
    def _compute_name(self):
        """Compute a descriptive name for the synchronization job"""
        for job in self:
            if job.site_id and job.start_time:
                start_time_str = fields.Datetime.to_string(job.start_time)
                job.name = f"{job.site_id.name} - {job.sync_type.capitalize()} Sync - {start_time_str}"
            else:
                job.name = f"New Sync Job"
    
    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        """Compute the duration of the synchronization job"""
        for job in self:
            if job.start_time and job.end_time:
                delta = job.end_time - job.start_time
                job.duration = delta.total_seconds()
            else:
                job.duration = 0
    
    @api.depends('log_ids')
    def _compute_api_call_count(self):
        """Compute the number of API calls made during this job"""
        for job in self:
            job.api_call_count = len(job.log_ids)
    
    @api.depends('log_ids', 'log_ids.success')
    def _compute_success_rate(self):
        """Compute the success rate of API calls"""
        for job in self:
            if job.api_call_count > 0:
                successful_calls = len(job.log_ids.filtered(lambda l: l.success))
                job.success_rate = (successful_calls / job.api_call_count) * 100
            else:
                job.success_rate = 0
    
    def action_cancel(self):
        """Cancel the synchronization job"""
        self.ensure_one()
        
        if self.state in ['pending', 'running']:
            self.write({
                'state': 'cancelled',
                'end_time': fields.Datetime.now()
            })
        
        return True
    
    def action_retry(self):
        """Retry a failed synchronization job"""
        self.ensure_one()
        
        if self.state in ['failed', 'cancelled']:
            # Create a new job
            new_job = self.copy({
                'state': 'pending',
                'start_time': fields.Datetime.now(),
                'end_time': False,
                'error_message': False,
                'created_records': 0,
                'updated_records': 0,
                'deleted_records': 0
            })
            
            # Start the new job
            new_job.start()
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'unifi.sync.job',
                'res_id': new_job.id,
                'view_mode': 'form',
                'target': 'current',
            }
        
        return True
    
    def action_view_logs(self):
        """View API logs for this synchronization job"""
        self.ensure_one()
        
        return {
            'name': _('API Logs'),
            'view_mode': 'tree,form',
            'res_model': 'unifi.api.log',
            'domain': [('sync_job_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_sync_job_id': self.id}
        }
    
    def start(self):
        """Start the synchronization job"""
        self.ensure_one()
        
        if self.state == 'pending':
            self.write({
                'state': 'running',
                'start_time': fields.Datetime.now()
            })
            
            # Trigger the synchronization on the site
            try:
                self.site_id.with_context(sync_job_id=self.id).action_sync_now()
                
                # If we get here, the sync was successful
                self.write({
                    'state': 'completed',
                    'end_time': fields.Datetime.now()
                })
            except Exception as e:
                # If an error occurred, mark the job as failed
                self.write({
                    'state': 'failed',
                    'end_time': fields.Datetime.now(),
                    'error_message': str(e)
                })
                _logger.error('Error during synchronization job: %s', str(e))
        
        return True
    
    @api.model
    def run_scheduled_sync(self):
        """Run scheduled synchronization jobs
        
        This method is called by a scheduled action to synchronize sites
        that have auto_sync enabled and are due for synchronization.
        
        Returns:
            bool: True if successful
        """
        # Find sites that are due for synchronization
        sites = self.env['unifi.site'].search([
            ('active', '=', True),
            ('auto_sync', '=', True)
        ])
        
        for site in sites:
            # Check if the site is due for synchronization
            if not site.last_sync or (fields.Datetime.now() - site.last_sync).total_seconds() / 60 >= site.sync_interval:
                # Create a new sync job
                sync_job = self.create({
                    'site_id': site.id,
                    'sync_type': 'scheduled',
                    'state': 'pending'
                })
                
                # Start the sync job
                sync_job.start()
        
        return True
    
    def log_record_changes(self, created=0, updated=0, deleted=0):
        """Log record changes during synchronization
        
        Args:
            created (int, optional): Number of records created
            updated (int, optional): Number of records updated
            deleted (int, optional): Number of records deleted
            
        Returns:
            bool: True if successful
        """
        self.ensure_one()
        
        self.write({
            'created_records': self.created_records + created,
            'updated_records': self.updated_records + updated,
            'deleted_records': self.deleted_records + deleted
        })
        
        return True
