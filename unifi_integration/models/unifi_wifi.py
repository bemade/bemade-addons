# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
from .unifi_common import UnifiCommonMixin
from odoo.exceptions import UserError, ValidationError
# pylint: enable=import-error

import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class UnifiWifi(models.Model, UnifiCommonMixin):
    """Model for UniFi WiFi networks
    
    This model represents WiFi networks configured in UniFi sites.
    It stores configuration details such as SSID, password, security type, etc.
    """
    _name = 'unifi.wifi'
    _description = 'UniFi WiFi Network'
    _order = 'name'
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this record is active in Odoo'
    )
    
    # Basic information
    name = fields.Char(
        string='Name',
        required=True,
        help='Name of the WiFi network (SSID)'
    )
    
    wifi_id = fields.Char(
        string='WiFi ID',
        required=True,
        help='Unique identifier for this WiFi network in the UniFi system'
    )
    
    # WiFi configuration
    enabled = fields.Boolean(
        string='Enabled',
        default=True,
        help='Whether this WiFi network is enabled'
    )
    
    hidden = fields.Boolean(
        string='Hidden SSID',
        default=False,
        help='Whether this SSID is hidden from network scans'
    )
    
    security = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('wep', 'WEP'),
            ('wpapsk', 'WPA Personal'),
            ('wpa2psk', 'WPA2 Personal'),
            ('wpapskwpa2psk', 'WPA/WPA2 Personal'),
            ('wpa3', 'WPA3 Personal'),
            ('wpa2enterprise', 'WPA2 Enterprise'),
            ('wpa3enterprise', 'WPA3 Enterprise'),
            ('radius', 'RADIUS')
        ],
        string='Security Type',
        default='wpa2psk',
        help='Security protocol used by this WiFi network'
    )
    
    password = fields.Char(
        string='Password',
        help='Password for this WiFi network (stored securely)'
    )
    
    # Network configuration
    network_id = fields.Many2one(
        comodel_name='unifi.network',
        string='Network',
        help='Network associated with this WiFi'
    )
    
    vlan_id = fields.Many2one(
        comodel_name='unifi.vlan',
        string='VLAN',
        help='VLAN associated with this WiFi'
    )
    
    # WiFi settings
    band = fields.Selection(
        selection=[
            ('2g', '2.4 GHz'),
            ('5g', '5 GHz'),
            ('both', '2.4 & 5 GHz')
        ],
        string='Band',
        default='both',
        help='WiFi frequency band'
    )
    
    channel = fields.Integer(
        string='Channel',
        help='WiFi channel (0 for auto)'
    )
    
    channel_width = fields.Selection(
        selection=[
            ('20', '20 MHz'),
            ('40', '40 MHz'),
            ('80', '80 MHz'),
            ('160', '160 MHz')
        ],
        string='Channel Width',
        help='WiFi channel width'
    )
    
    tx_power = fields.Selection(
        selection=[
            ('auto', 'Auto'),
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('custom', 'Custom')
        ],
        string='TX Power',
        default='auto',
        help='Transmission power'
    )
    
    tx_power_custom = fields.Integer(
        string='Custom TX Power',
        help='Custom transmission power in dBm'
    )
    
    # Guest network settings
    is_guest = fields.Boolean(
        string='Guest Network',
        default=False,
        help='Whether this is a guest WiFi network'
    )
    
    guest_policy = fields.Selection(
        selection=[
            ('none', 'No restrictions'),
            ('mac', 'MAC filtering'),
            ('auth', 'Authentication required')
        ],
        string='Guest Policy',
        default='none',
        help='Access policy for guest networks'
    )
    
    # Advanced settings
    wpa_mode = fields.Selection(
        selection=[
            ('wpa', 'WPA'),
            ('wpa2', 'WPA2'),
            ('wpa3', 'WPA3'),
            ('wpa/wpa2', 'WPA/WPA2'),
            ('wpa2/wpa3', 'WPA2/WPA3')
        ],
        string='WPA Mode',
        help='WPA mode for this network'
    )
    
    wpa_encryption = fields.Selection(
        selection=[
            ('auto', 'Auto'),
            ('ccmp', 'CCMP (AES)'),
            ('tkip', 'TKIP'),
            ('tkip-ccmp', 'TKIP/CCMP')
        ],
        string='WPA Encryption',
        default='auto',
        help='Encryption method used for WPA'
    )
    
    pmf_mode = fields.Selection(
        selection=[
            ('disabled', 'Disabled'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        string='PMF Mode',
        default='optional',
        help='Protected Management Frames mode'
    )
    
    # Tracking fields
    created_at = fields.Datetime(
        string='Created At',
        default=fields.Datetime.now,
        help='When this record was created in Odoo'
    )
    
    updated_at = fields.Datetime(
        string='Updated At',
        help='When this record was last updated in Odoo'
    )
    
    last_sync = fields.Datetime(
        string='Last Sync',
        help='When this record was last synchronized with UniFi'
    )
    
    # Raw data
    raw_data = fields.Text(
        string='Raw Data',
        help='Raw JSON data from UniFi API'
    )
    
    raw_data_json = fields.Text(
        string='Données brutes (JSON)',
        compute='_compute_raw_data_json',
        help='Données brutes de la configuration WiFi au format JSON formaté'
    )
    
    @api.depends('raw_data')
    def _compute_raw_data_json(self):
        for record in self:
            record.raw_data_json = self.format_raw_data_json(record.raw_data)
    
    # Relations
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='UniFi site this WiFi network belongs to'
    )
    
    # Methods
    def create_or_update_from_data(self, site, wifi_data):
        """Create or update a WiFi network from API data
        
        Args:
            site: The UniFi site record
            wifi_data: The WiFi network data from the API
            
        Returns:
            record: The created or updated WiFi network record
        """
        # Extract the WiFi ID
        wifi_id = wifi_data.get('_id') or wifi_data.get('id')
        if not wifi_id:
            _logger.error("Cannot create/update WiFi network: missing ID")
            return False
        
        # Search for an existing WiFi network with this ID
        existing_wifi = self.search([
            ('wifi_id', '=', wifi_id),
            ('site_id', '=', site.id)
        ], limit=1)
        
        # Prepare values for creation/update
        vals = {
            'wifi_id': wifi_id,
            'name': wifi_data.get('name', wifi_data.get('ssid', f"WiFi {wifi_id}")),
            'site_id': site.id,
            'enabled': wifi_data.get('enabled', True),
            'hidden': wifi_data.get('hide_ssid', False),
            'security': self._map_security_type(wifi_data.get('security', 'wpa2psk')),
            'is_guest': wifi_data.get('is_guest', False),
            'band': self._map_band(wifi_data.get('band', 'both')),
            'last_sync': fields.Datetime.now(),
            'raw_data': json.dumps(wifi_data)
        }
        
        # Add password if available (and not empty)
        if wifi_data.get('x_passphrase') and wifi_data.get('x_passphrase') != 'null':
            vals['password'] = wifi_data.get('x_passphrase')
        
        # Map network and VLAN if available
        if wifi_data.get('networkconf_id'):
            network = self.env['unifi.network'].search([
                ('network_id', '=', wifi_data.get('networkconf_id')),
                ('site_id', '=', site.id)
            ], limit=1)
            if network:
                vals['network_id'] = network.id
        
        if wifi_data.get('vlan_id'):
            vlan = self.env['unifi.vlan'].search([
                ('vlan_id', '=', wifi_data.get('vlan_id')),
                ('site_id', '=', site.id)
            ], limit=1)
            if vlan:
                vals['vlan_id'] = vlan.id
        
        # Add advanced settings if available
        if 'channel' in wifi_data:
            vals['channel'] = wifi_data.get('channel')
        
        if 'channel_width' in wifi_data:
            vals['channel_width'] = str(wifi_data.get('channel_width', '20'))
        
        if 'tx_power' in wifi_data:
            vals['tx_power'] = self._map_tx_power(wifi_data.get('tx_power'))
        
        if 'tx_power_mode' in wifi_data and wifi_data.get('tx_power_mode') == 'custom':
            vals['tx_power'] = 'custom'
            vals['tx_power_custom'] = wifi_data.get('tx_power')
        
        # WPA settings
        if 'wpa_mode' in wifi_data:
            vals['wpa_mode'] = self._map_wpa_mode(wifi_data.get('wpa_mode'))
        
        if 'wpa_enc' in wifi_data:
            vals['wpa_encryption'] = self._map_wpa_encryption(wifi_data.get('wpa_enc'))
        
        if 'pmf_mode' in wifi_data:
            vals['pmf_mode'] = self._map_pmf_mode(wifi_data.get('pmf_mode'))
        
        if existing_wifi:
            # Update existing WiFi network
            vals['updated_at'] = fields.Datetime.now()
            existing_wifi.write(vals)
            return existing_wifi
        else:
            # Create new WiFi network
            return self.create(vals)
    
    def _map_security_type(self, security):
        """Map UniFi security type to model selection value
        
        Args:
            security: Security type from UniFi API
            
        Returns:
            str: Mapped security type
        """
        security_map = {
            'open': 'open',
            'wep': 'wep',
            'wpapsk': 'wpapsk',
            'wpa2psk': 'wpa2psk',
            'wpapskwpa2psk': 'wpapskwpa2psk',
            'wpa3': 'wpa3',
            'wpa2enterprise': 'wpa2enterprise',
            'wpa3enterprise': 'wpa3enterprise',
            'radius': 'radius'
        }
        return security_map.get(security, 'wpa2psk')
    
    def _map_band(self, band):
        """Map UniFi band to model selection value
        
        Args:
            band: Band from UniFi API
            
        Returns:
            str: Mapped band
        """
        band_map = {
            'ng': '2g',
            '2g': '2g',
            'na': '5g',
            '5g': '5g',
            'both': 'both',
            'all': 'both'
        }
        return band_map.get(band, 'both')
    
    def _map_tx_power(self, tx_power):
        """Map UniFi TX power to model selection value
        
        Args:
            tx_power: TX power from UniFi API
            
        Returns:
            str: Mapped TX power
        """
        # If it's already a string value that matches our selection options
        if tx_power in ['auto', 'low', 'medium', 'high', 'custom']:
            return tx_power
        
        # If it's a numeric value, map it to a named level
        try:
            power = int(tx_power)
            if power <= 10:
                return 'low'
            elif power <= 18:
                return 'medium'
            else:
                return 'high'
        except (ValueError, TypeError):
            return 'auto'
    
    def _map_wpa_mode(self, wpa_mode):
        """Map UniFi WPA mode to model selection value
        
        Args:
            wpa_mode: WPA mode from UniFi API
            
        Returns:
            str: Mapped WPA mode
        """
        wpa_mode_map = {
            '1': 'wpa',
            '2': 'wpa2',
            '3': 'wpa3',
            '12': 'wpa/wpa2',
            '23': 'wpa2/wpa3'
        }
        return wpa_mode_map.get(str(wpa_mode), 'wpa2')
    
    def _map_wpa_encryption(self, wpa_enc):
        """Map UniFi WPA encryption to model selection value
        
        Args:
            wpa_enc: WPA encryption from UniFi API
            
        Returns:
            str: Mapped WPA encryption
        """
        wpa_enc_map = {
            'auto': 'auto',
            'ccmp': 'ccmp',
            'tkip': 'tkip',
            'tkip-ccmp': 'tkip-ccmp',
            'tkip,ccmp': 'tkip-ccmp'
        }
        return wpa_enc_map.get(wpa_enc, 'auto')
    
    def _map_pmf_mode(self, pmf_mode):
        """Map UniFi PMF mode to model selection value
        
        Args:
            pmf_mode: PMF mode from UniFi API
            
        Returns:
            str: Mapped PMF mode
        """
        pmf_mode_map = {
            '0': 'disabled',
            '1': 'optional',
            '2': 'required',
            'disabled': 'disabled',
            'optional': 'optional',
            'required': 'required'
        }
        return pmf_mode_map.get(str(pmf_mode), 'optional')
