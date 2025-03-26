# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
# pylint: enable=import-error

import logging
import json

_logger = logging.getLogger(__name__)

class UnifiApiLog(models.Model):
    """Logs API calls to UniFi APIs
    
    This model stores information about API calls made to both the Site Manager API
    and Controller API, including request details, response status, and timing.
    """
    _name = 'unifi.api.log'
    _description = 'UniFi API Log'
    _order = 'create_date desc'
    
    @api.onchange('site_id')
    def onchange(self, values=None, field_names=None, fields_spec=None):
        """Implémentation de la méthode abstraite onchange de BaseModel
        
        Cette méthode est déclenchée lorsque le site_id change. Elle peut être utilisée
        pour mettre à jour d'autres champs en fonction du site sélectionné.
        
        Args:
            values: Dictionnaire des valeurs modifiées
            field_names: Noms des champs modifiés
            fields_spec: Spécification des champs à mettre à jour
            
        Returns:
            Un dictionnaire des valeurs à mettre à jour
        """
        # Actuellement, aucune action spécifique n'est nécessaire lors du changement de site
        # Cette méthode est implémentée pour satisfaire l'exigence de la classe abstraite
        return {}
    
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='The site this API call was made for'
    )
    
    api_config_id = fields.Many2one(
        comodel_name='unifi.api.config',
        string='Configuration API',
        ondelete='cascade',
        help='Configuration API utilisée pour cet appel API'
    )
    
    sync_job_id = fields.Many2one(
        comodel_name='unifi.sync.job',
        string='Sync Job',
        ondelete='cascade',
        help='The synchronization job that triggered this API call'
    )
    
    api_type = fields.Selection(
        selection=[
            ('site_manager', 'Site Manager API'),
            ('controller', 'Controller API')
        ],
        string='API Type',
        required=True,
        help='Type of API used for this call'
    )
    
    endpoint = fields.Char(
        string='Endpoint',
        required=True,
        help='API endpoint that was called'
    )
    
    method = fields.Selection(
        selection=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('DELETE', 'DELETE'),
            ('PATCH', 'PATCH')
        ],
        string='HTTP Method',
        required=True,
        help='HTTP method used for the API call'
    )
    
    request_params = fields.Text(
        string='Request Parameters',
        help='Parameters sent with the request (JSON)'
    )
    
    request_headers = fields.Text(
        string='Request Headers',
        help='Headers sent with the request (JSON)'
    )
    
    request_body = fields.Text(
        string='Request Body',
        help='Body sent with the request (JSON)'
    )
    
    status_code = fields.Integer(
        string='Status Code',
        help='HTTP status code returned by the API'
    )
    
    response_headers = fields.Text(
        string='Response Headers',
        help='Headers returned by the API (JSON)'
    )
    
    response_body = fields.Text(
        string='Response Body',
        help='Body returned by the API (JSON)'
    )
    
    duration = fields.Float(
        string='Duration (ms)',
        help='Time taken to complete the API call in milliseconds'
    )
    
    success = fields.Boolean(
        string='Success',
        compute='_compute_success',
        store=True,
        help='Whether the API call was successful'
    )
    
    error_message = fields.Text(
        string='Error Message',
        help='Error message if the API call failed'
    )
    
    create_date = fields.Datetime(
        string='Created On',
        readonly=True,
        help='Date and time when this log was created'
    )
    
    start_time = fields.Datetime(
        string='Start Time',
        help='Date and time when the API call started'
    )
    
    end_time = fields.Datetime(
        string='End Time',
        help='Date and time when the API call completed'
    )
    
    request_formatted = fields.Text(
        string='Formatted Request',
        compute='_compute_formatted_data',
        store=False,
        help='Formatted representation of the request'
    )
    
    response_formatted = fields.Text(
        string='Formatted Response',
        compute='_compute_formatted_data',
        store=False,
        help='Formatted representation of the response'
    )
    
    @api.depends('status_code')
    def _compute_success(self):
        """Compute whether the API call was successful based on status code"""
        for log in self:
            log.success = log.status_code and 200 <= log.status_code < 300
    
    @api.model
    def log_api_call(self, site_id, api_type, endpoint, method, request_params=None, 
                    request_headers=None, request_body=None, status_code=None, 
                    response_headers=None, response_body=None, duration=0, 
                    error_message=None, sync_job_id=None):
        """Create a new API log entry
        
        Args:
            site_id (int): ID of the site
            api_type (str): Type of API ('site_manager' or 'controller')
            endpoint (str): API endpoint
            method (str): HTTP method
            request_params (dict, optional): Request parameters
            request_headers (dict, optional): Request headers
            request_body (dict, optional): Request body
            status_code (int, optional): HTTP status code
            response_headers (dict, optional): Response headers
            response_body (dict, optional): Response body
            duration (float, optional): Duration in milliseconds
            error_message (str, optional): Error message
            sync_job_id (int, optional): ID of the sync job
            
        Returns:
            unifi.api.log: The created log record
        """
        # Convert dictionaries to JSON strings
        if request_params and isinstance(request_params, dict):
            request_params = json.dumps(request_params)
        
        if request_headers and isinstance(request_headers, dict):
            request_headers = json.dumps(request_headers)
        
        if request_body and isinstance(request_body, dict):
            request_body = json.dumps(request_body)
        
        if response_headers and isinstance(response_headers, dict):
            response_headers = json.dumps(response_headers)
        
        if response_body and isinstance(response_body, dict):
            response_body = json.dumps(response_body)
        
        # Create the log
        return self.create({
            'site_id': site_id,
            'api_type': api_type,
            'endpoint': endpoint,
            'method': method,
            'request_params': request_params,
            'request_headers': request_headers,
            'request_body': request_body,
            'status_code': status_code,
            'response_headers': response_headers,
            'response_body': response_body,
            'duration': duration,
            'error_message': error_message,
            'sync_job_id': sync_job_id,
        })
    
    def get_formatted_request(self):
        """Get a formatted representation of the request
        
        Returns:
            str: Formatted request details
        """
        self.ensure_one()
        
        result = f"{self.method} {self.endpoint}\n"
        
        if self.request_headers:
            try:
                headers = json.loads(self.request_headers)
                result += "Headers:\n"
                for key, value in headers.items():
                    result += f"  {key}: {value}\n"
            except:
                result += f"Headers: {self.request_headers}\n"
        
        if self.request_params:
            try:
                params = json.loads(self.request_params)
                result += "Parameters:\n"
                for key, value in params.items():
                    result += f"  {key}: {value}\n"
            except:
                result += f"Parameters: {self.request_params}\n"
        
        if self.request_body:
            try:
                body = json.loads(self.request_body)
                result += f"Body: {json.dumps(body, indent=2)}\n"
            except:
                result += f"Body: {self.request_body}\n"
        
        return result
    
    def get_formatted_response(self):
        """Get a formatted representation of the response
        
        Returns:
            str: Formatted response details
        """
        self.ensure_one()
        
        result = f"Status: {self.status_code}\n"
        
        if self.response_headers:
            try:
                headers = json.loads(self.response_headers)
                result += "Headers:\n"
                for key, value in headers.items():
                    result += f"  {key}: {value}\n"
            except:
                result += f"Headers: {self.response_headers}\n"
        
        if self.response_body:
            try:
                body = json.loads(self.response_body)
                result += f"Body: {json.dumps(body, indent=2)}\n"
            except:
                result += f"Body: {self.response_body}\n"
        
        if self.error_message:
            result += f"Error: {self.error_message}\n"
        
        return result
        
    @api.depends('request_headers', 'request_params', 'request_body', 'response_headers', 'response_body', 'error_message')
    def _compute_formatted_data(self):
        """Compute formatted representations of request and response data"""
        for log in self:
            log.request_formatted = log.get_formatted_request()
            log.response_formatted = log.get_formatted_response()
