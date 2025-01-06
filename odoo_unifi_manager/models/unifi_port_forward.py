from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re
from datetime import datetime
import logging

class PortForwardRule(models.Model):
    _name = 'unifi.port.forward'
    _description = 'UniFi Port Forward Rule'
    _order = 'name'

    name = fields.Char(
        string='Rule Name', 
        required=True
    )

    unifi_id = fields.Char(
        string='UniFi ID',
        readonly=True
    )

    last_sync = fields.Datetime(
        string='Last Synchronization',
        readonly=True
    )

    enabled = fields.Boolean(
        string='Enabled',
        default=True,
        help="Enable or disable this rule"
    )

    description = fields.Text(
        string='Description',
        help="Detailed description of the rule's purpose"
    )

    controller_id = fields.Many2one(
        'unifi.ctrl', 
        string='Controller', 
        required=True, 
        help="Controller where this rule is applied"
    )

    # Port Forward specific fields
    dst_port = fields.Char(
        string='Destination Port',
        required=True,
        help="Port or port range (e.g., '80' or '80:85')"
    )

    fwd_port = fields.Char(
        string='Forward Port',
        required=True,
        help="Port or port range to forward to"
    )

    fwd_ip = fields.Char(
        string='Forward IP',
        required=True,
        help="IP address to forward to"
    )

    protocol = fields.Selection([
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('tcp_udp', 'TCP & UDP')
    ], string='Protocol', required=True, default='tcp')

    src = fields.Char(
        string='Source',
        help="Source address/network (e.g., '192.168.1.0/24' or 'any')"
    )

    dst = fields.Char(
        string='Destination',
        help="Destination address/network"
    )

    log = fields.Boolean(
        string='Log',
        default=False,
        help="Enable logging for this rule"
    )

    @api.constrains('fwd_ip')
    def _check_fwd_ip(self):
        """Validate forward IP format."""
        for record in self:
            if record.fwd_ip:
                try:
                    # Vérifier que c'est une adresse IPv4 valide
                    parts = record.fwd_ip.split('.')
                    if len(parts) != 4:
                        raise ValueError
                    for part in parts:
                        num = int(part)
                        if not (0 <= num <= 255):
                            raise ValueError
                except (ValueError, AttributeError):
                    raise ValidationError(f"Invalid forward IP: {record.fwd_ip}. Must be a valid IPv4 address (e.g., 192.168.1.100)")

    @api.constrains('dst_port', 'fwd_port')
    def _check_ports(self):
        """Validate port format."""
        _logger = logging.getLogger(__name__)
        for record in self:
            # Log les valeurs pour le débogage
            _logger.info(f"Validating ports - dst_port: '{record.dst_port}', fwd_port: '{record.fwd_port}'")
            
            def is_valid_port(port_str):
                """Vérifie si un port est valide."""
                if not port_str or port_str == 'any':
                    return True
                
                # Nettoyer la chaîne
                port_str = port_str.strip()
                
                # Remplacer le tiret par deux-points si présent
                if '-' in port_str:
                    port_str = port_str.replace('-', ':')
                
                try:
                    # Essayer de convertir en nombre unique
                    port = int(port_str)
                    return 1 <= port <= 65535
                except ValueError:
                    try:
                        # Essayer de traiter comme une plage
                        start, end = map(int, port_str.split(':'))
                        return 1 <= start <= 65535 and 1 <= end <= 65535 and start <= end
                    except (ValueError, TypeError):
                        return False
            
            if record.dst_port and not is_valid_port(record.dst_port):
                raise ValidationError(f"Invalid destination port: {record.dst_port}. Must be a number between 1-65535 or a range (e.g., '80:85' or '80-85')")
            
            if record.fwd_port and not is_valid_port(record.fwd_port):
                raise ValidationError(f"Invalid forward port: {record.fwd_port}. Must be a number between 1-65535 or a range (e.g., '80:85' or '80-85')")

    @classmethod
    def from_unifi_dict(cls, env, controller, data):
        """Create a port forward rule from UniFi data."""
        # Log pour le débogage
        _logger = logging.getLogger(__name__)
        _logger.info(f"Converting UniFi data to port forward: {data}")

        def format_port(port_value):
            """Format port value to string, handling various input types."""
            _logger.info(f"Formatting port value: {port_value} of type {type(port_value)}")
            if port_value is None:
                return ''
            
            # Convertir en chaîne et nettoyer
            port_str = str(port_value).strip()
            
            # Convertir le format tiret en format deux-points pour les plages
            if '-' in port_str:
                port_str = port_str.replace('-', ':')
            
            return port_str

        # Dans l'API UniFi:
        # - dst_port : port de destination externe
        # - fwd : IP de destination interne
        # - fwd_port : port de destination interne (si différent de dst_port)
        values = {
            'controller_id': controller.id,
            'unifi_id': data.get('_id'),
            'name': data.get('name', 'Unnamed Rule'),
            'enabled': data.get('enabled', True),
            'dst_port': format_port(data.get('dst_port')),
            'fwd_port': format_port(data.get('dst_port')),  # Par défaut, même port que dst_port
            'fwd_ip': data.get('fwd', ''),  # L'IP est dans le champ 'fwd'
            'protocol': data.get('proto', 'tcp'),
            'src': data.get('src', 'any'),
            'dst': data.get('dst', 'any'),
            'log': data.get('log', False),
            'last_sync': datetime.now()
        }
        
        # Si un port de destination interne spécifique est défini, l'utiliser
        if 'fwd_port' in data:
            values['fwd_port'] = format_port(data['fwd_port'])
        
        _logger.info(f"Converted values: {values}")
        return values

    def to_unifi_dict(self):
        """Convert the record to a UniFi-compatible dictionary."""
        self.ensure_one()
        
        def format_port_for_unifi(port_str):
            """Convert port format back to UniFi format."""
            if port_str and ':' in port_str:
                return port_str.replace(':', '-')
            return port_str
        
        return {
            '_id': self.unifi_id or None,
            'name': self.name,
            'enabled': self.enabled,
            'dst_port': format_port_for_unifi(self.dst_port),
            'fwd': self.fwd_ip,
            'fwd_port': format_port_for_unifi(self.fwd_port) if self.fwd_port != self.dst_port else None,
            'proto': self.protocol,
            'src': self.src or 'any',
            'dst': self.dst or 'any',
            'log': self.log
        }
