from odoo import models, fields, api
from odoo.exceptions import ValidationError
import ipaddress

class UnifiFirewallGroup(models.Model):
    _name = 'unifi.firewall.group'
    _description = 'UniFi Firewall Group'

    name = fields.Char(
        string='Name',
        required=True
    )

    ctrl_id = fields.Many2one(
        'unifi.ctrl',
        string='Controller',
        required=True
    )

    group_type = fields.Selection([
        ('address-group', 'Address Group'),
        ('port-group', 'Port Group'),
        ('ipv6-address-group', 'IPv6 Address Group')
    ], string='Group Type', required=True)

    members = fields.Text(
        string='Members',
        help="One entry per line. For address groups: IP/CIDR. For port groups: port or port range"
    )

    description = fields.Text(
        string='Description'
    )

    rule_ids = fields.One2many(
        'unifi.firewall.rule.template',
        'firewall_group_id',
        string='Associated Rules'
    )

    @api.constrains('members', 'group_type')
    def _validate_members(self):
        """Validate member format based on group type."""
        for record in self:
            if not record.members:
                continue

            members = record.members.split('\n')
            if record.group_type in ['address-group', 'ipv6-address-group']:
                for member in members:
                    member = member.strip()
                    if not member:
                        continue
                    try:
                        ipaddress.ip_network(member)
                    except ValueError:
                        raise ValidationError(f"Invalid IP address or network: {member}")
            
            elif record.group_type == 'port-group':
                for member in members:
                    member = member.strip()
                    if not member:
                        continue
                    if '-' in member:
                        try:
                            start, end = map(int, member.split('-'))
                            if not (1 <= start <= end <= 65535):
                                raise ValidationError(f"Invalid port range: {member}")
                        except ValueError:
                            raise ValidationError(f"Invalid port range format: {member}")
                    else:
                        try:
                            port = int(member)
                            if not (1 <= port <= 65535):
                                raise ValidationError(f"Invalid port number: {member}")
                        except ValueError:
                            raise ValidationError(f"Invalid port format: {member}")

    def copy_to_controller(self):
        """Copy this group to the UniFi controller."""
        self.ensure_one()
        client = self.ctrl_id.get_client()
        
        group_data = {
            'name': self.name,
            'group_type': self.group_type,
            'group_members': [m.strip() for m in self.members.split('\n') if m.strip()],
        }
        
        if self.description:
            group_data['group_description'] = self.description
            
        return client.create_firewall_group(group_data)
