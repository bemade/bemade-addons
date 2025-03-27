# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from .unifi_common import UnifiCommonMixin
from odoo.exceptions import ValidationError
import logging
import json
from pprint import pformat

_logger = logging.getLogger(__name__)

class UnifiVpn(models.Model, UnifiCommonMixin):
    """Configuration VPN pour le système UniFi
    
    Ce modèle stocke les configurations VPN pour les contrôleurs UniFi.
    Il gère les tunnels VPN IPsec et autres types de VPN.
    
    Les configurations VPN sont liées à un site spécifique et sont automatiquement supprimées
    lorsque le site est supprimé (cascade).
    """
    _name = 'unifi.vpn'
    _description = 'UniFi VPN Configuration'
    _rec_name = 'name'
    _order = 'name'
    
    site_id = fields.Many2one(
        comodel_name='unifi.site', 
        string='Site', 
        required=True,
        ondelete='cascade',
        help='Site this VPN configuration belongs to'
    )
    
    name = fields.Char(
        string='Name',
        required=True,
        help='Name of this VPN configuration'
    )
    
    vpn_type = fields.Selection(
        selection=[
            ('ipsec-vpn', 'IPsec VPN'),
            ('l2tp-vpn', 'L2TP VPN'),
            ('openvpn', 'OpenVPN'),
            ('wireguard', 'WireGuard'),
            ('other', 'Other')
        ],
        string='VPN Type',
        default='ipsec-vpn',
        help='Type of VPN connection'
    )
    
    enabled = fields.Boolean(
        string='Enabled',
        default=True,
        help='Whether this VPN configuration is active'
    )
    
    peer_ip = fields.Char(
        string='Peer IP',
        help='IP address of the remote VPN peer'
    )
    
    local_ip = fields.Char(
        string='Local IP',
        help='Local IP address for this VPN connection'
    )
    
    remote_subnets = fields.Char(
        string='Remote Subnets',
        help='Comma-separated list of remote subnets accessible through this VPN'
    )
    
    interface = fields.Char(
        string='Interface',
        help='Network interface used for this VPN'
    )
    
    purpose = fields.Char(
        string='Purpose',
        help='Purpose of this VPN connection'
    )
    
    unifi_id = fields.Char(
        string='UniFi ID',
        help='ID of this VPN configuration in the UniFi system'
    )
    
    last_sync = fields.Datetime(
        string='Last Synchronization',
        help='Last time this VPN configuration was synchronized with the UniFi system'
    )
    
    raw_data = fields.Text(
        string='Raw Data',
        help='Raw VPN configuration data in JSON format'
    )
    
    raw_data_json = fields.Text(
        string='Données brutes (JSON)',
        compute='_compute_raw_data_json',
        help='Données brutes de la configuration VPN au format JSON formaté'
    )
    
    @api.depends('raw_data')
    def _compute_raw_data_json(self):
        for record in self:
            record.raw_data_json = self.format_raw_data_json(record.raw_data)
    
    formatted_data = fields.Html(
        string='Formatted Configuration',
        compute='_compute_formatted_data',
        help='Formatted view of the VPN configuration data'
    )
    
    @api.depends('raw_data')
    def _compute_formatted_data(self):
        """Transforme les données brutes JSON en format HTML lisible"""
        for record in self:
            if not record.raw_data:
                record.formatted_data = "<p><em>Aucune donnée disponible</em></p>"
                continue
                
            try:
                # Analyser les données JSON
                data = json.loads(record.raw_data)
                
                # Créer une représentation HTML formatée
                html = "<div style='font-family: monospace;'>"
                
                # Informations générales
                html += "<h3 style='color: #2C3E50;'>Informations générales</h3>"
                html += "<table style='width: 100%; border-collapse: collapse;'>"
                html += f"<tr><td style='padding: 4px; font-weight: bold;'>Nom:</td><td>{data.get('name', 'N/A')}</td></tr>"
                html += f"<tr><td style='padding: 4px; font-weight: bold;'>Type:</td><td>{data.get('vpn_type', 'N/A')}</td></tr>"
                html += f"<tr><td style='padding: 4px; font-weight: bold;'>Activé:</td><td>{'Oui' if data.get('enabled') else 'Non'}</td></tr>"
                html += f"<tr><td style='padding: 4px; font-weight: bold;'>Interface:</td><td>{data.get('ifname', 'N/A')}</td></tr>"
                html += f"<tr><td style='padding: 4px; font-weight: bold;'>But:</td><td>{data.get('purpose', 'N/A')}</td></tr>"
                html += "</table>"
                
                # Configuration IPsec
                if data.get('vpn_type') == 'ipsec-vpn':
                    html += "<h3 style='color: #2C3E50; margin-top: 15px;'>Configuration IPsec</h3>"
                    html += "<table style='width: 100%; border-collapse: collapse;'>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>IP Pair:</td><td>{data.get('ipsec_peer_ip', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>IP Locale:</td><td>{data.get('ipsec_local_ip', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Interface:</td><td>{data.get('ipsec_interface', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Échange de clés:</td><td>{data.get('ipsec_key_exchange', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Profil:</td><td>{data.get('ipsec_profile', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>PFS:</td><td>{'Oui' if data.get('ipsec_pfs') else 'Non'}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Routage dynamique:</td><td>{'Oui' if data.get('ipsec_dynamic_routing') else 'Non'}</td></tr>"
                    html += "</table>"
                    
                    # Paramètres IKE
                    html += "<h4 style='color: #2C3E50; margin-top: 10px;'>Paramètres IKE</h4>"
                    html += "<table style='width: 100%; border-collapse: collapse;'>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Groupe DH:</td><td>{data.get('ipsec_ike_dh_group', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Chiffrement:</td><td>{data.get('ipsec_ike_encryption', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Hash:</td><td>{data.get('ipsec_ike_hash', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Durée de vie (s):</td><td>{data.get('ipsec_ike_lifetime', 'N/A')}</td></tr>"
                    html += "</table>"
                    
                    # Paramètres ESP
                    html += "<h4 style='color: #2C3E50; margin-top: 10px;'>Paramètres ESP</h4>"
                    html += "<table style='width: 100%; border-collapse: collapse;'>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Groupe DH:</td><td>{data.get('ipsec_esp_dh_group', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Chiffrement:</td><td>{data.get('ipsec_esp_encryption', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Hash:</td><td>{data.get('ipsec_esp_hash', 'N/A')}</td></tr>"
                    html += f"<tr><td style='padding: 4px; font-weight: bold;'>Durée de vie (s):</td><td>{data.get('ipsec_esp_lifetime', 'N/A')}</td></tr>"
                    html += "</table>"
                
                # Sous-réseaux distants
                remote_subnets = data.get('remote_vpn_subnets', [])
                if remote_subnets:
                    html += "<h3 style='color: #2C3E50; margin-top: 15px;'>Sous-réseaux distants</h3>"
                    html += "<ul style='margin-top: 5px;'>"
                    for subnet in remote_subnets:
                        html += f"<li>{subnet}</li>"
                    html += "</ul>"
                
                html += "</div>"
                record.formatted_data = html
            except Exception as e:
                _logger.error("Erreur lors du formatage des données VPN: %s", str(e))
                record.formatted_data = f"<p><em>Erreur lors du formatage des données: {str(e)}</em></p>"
    
    @api.model
    def create_or_update_from_data(self, site, vpn_data):
        """Create or update VPN configuration from UniFi API data
        
        Args:
            site (unifi.site): Site record
            vpn_data (dict): VPN configuration data from UniFi API
            
        Returns:
            unifi.vpn: Created or updated VPN configuration record
        """
        _logger.info("Creating or updating VPN configuration from data")
        
        # Extract required fields
        name = vpn_data.get('name')
        vpn_type = vpn_data.get('vpn_type')
        unifi_id = vpn_data.get('_id')
        
        if not name or not vpn_type:
            _logger.warning("Missing required fields in VPN data")
            return False
        
        # Search for existing VPN configuration
        domain = [
            ('site_id', '=', site.id),
            '|',
            ('name', '=', name),
            ('unifi_id', '=', unifi_id)
        ]
        
        existing = self.search(domain, limit=1)
        
        # Prepare values for create/write
        vals = {
            'name': name,
            'vpn_type': vpn_type,
            'unifi_id': unifi_id,
            'enabled': vpn_data.get('enabled', True),
            'peer_ip': vpn_data.get('ipsec_peer_ip'),
            'local_ip': vpn_data.get('ipsec_local_ip'),
            'interface': vpn_data.get('ifname'),
            'purpose': vpn_data.get('purpose'),
            'remote_subnets': ', '.join(vpn_data.get('remote_vpn_subnets', [])),
            'last_sync': fields.Datetime.now(),
            'raw_data': json.dumps(vpn_data, indent=2) if vpn_data else False
        }
        
        if existing:
            _logger.info("Updating existing VPN configuration: %s", existing.name)
            existing.write(vals)
            return existing
        else:
            _logger.info("Creating new VPN configuration: %s", name)
            vals['site_id'] = site.id
            return self.create(vals)
