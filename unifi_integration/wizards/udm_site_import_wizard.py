# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import urllib3
from requests.exceptions import RequestException

class UdmSiteImportWizard(models.TransientModel):
    """Wizard to create a new site from a UDM Pro device"""
    _name = 'udm.site.import.wizard'
    _description = 'Import UDM Pro Site Wizard'

    name = fields.Char(string='Site Name', required=True)
    host = fields.Char(string='UDM Pro IP/Hostname', required=True)
    port = fields.Integer(string='Port', default=443)
    username = fields.Char(string='Username', required=True)
    password = fields.Char(string='Password', required=True)
    site_id = fields.Char(string='Site ID', default='default',
                         help="Site identifier in UniFi (usually 'default' unless configured otherwise)")

    def action_import_site(self):
        """Create a new site and configuration from UDM Pro"""
        self.ensure_one()

        try:
            # Disable SSL verification warnings - UDM Pro often uses self-signed certs
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            # Test connection to UDM Pro
            login_url = f'https://{self.host}:{self.port}/api/auth/login'
            login_data = {
                'username': self.username,
                'password': self.password
            }
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }

            response = requests.post(
                login_url,
                json=login_data,
                headers=headers,
                verify=False
            )
            response.raise_for_status()

            # Create the site
            site = self.env['udm.site'].create({
                'name': self.name,
                'site_id': self.site_id,
                'active': True
            })

            # Create the configuration
            config = self.env['udm.configuration'].create({
                'site_id': site.id,
                'host': self.host,
                'port': self.port,
                'username': self.username,
                'password': self.password,
                'active': True
            })

            # Import the configuration
            config.action_import_configuration()

            # Return action to view the new site
            return {
                'name': _('Site'),
                'view_mode': 'form',
                'res_model': 'udm.site',
                'res_id': site.id,
                'type': 'ir.actions.act_window',
                'target': 'current',
            }

        except RequestException as e:
            raise UserError(_('Failed to connect to UDM Pro: %s') % str(e))
        except Exception as e:
            raise UserError(_('Failed to create site: %s') % str(e))
