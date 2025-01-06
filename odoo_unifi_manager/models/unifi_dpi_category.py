from odoo import models, fields

class UnifiDPICategory(models.Model):
    _name = 'unifi.dpi.category'
    _description = 'UniFi DPI Category'

    name = fields.Char(string='Name', required=True)
    category_id = fields.Integer(string='Category ID', required=True)
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('unique_category_id', 'unique(category_id)', 'Category ID must be unique!')
    ]

    def _init_dpi_categories(self):
        """Initialize default DPI categories."""
        categories = [
            (0, 'Instant messaging', 'Instant messaging applications'),
            (1, 'P2P', 'Peer-to-peer file sharing'),
            (3, 'File Transfer', 'File transfer protocols'),
            (4, 'Streaming Media', 'Streaming media services'),
            (5, 'Mail and Collaboration', 'Email and collaboration tools'),
            (6, 'Voice over IP', 'Voice over IP services'),
            (7, 'Database', 'Database applications'),
            (8, 'Games', 'Online gaming'),
            (9, 'Network Management', 'Network management protocols'),
            (10, 'Remote Access Terminals', 'Remote access services'),
            (11, 'Bypass Proxies and Tunnels', 'Proxy and tunnel services'),
            (12, 'Stock Market', 'Stock market and trading'),
            (13, 'Web', 'Web browsing'),
            (14, 'Security Update', 'Security updates'),
            (15, 'Web IM', 'Web-based instant messaging'),
            (17, 'Business', 'Business applications'),
            (18, 'Network Protocols', 'Common network protocols'),
            (19, 'Network Protocols', 'Additional network protocols'),
            (20, 'Network Protocols', 'More network protocols'),
            (23, 'Private Protocol', 'Private protocols'),
            (24, 'Social Network', 'Social networking'),
            (255, 'Unknown', 'Unknown applications')
        ]

        for cat_id, name, description in categories:
            self.env['unifi.dpi.category'].create({
                'category_id': cat_id,
                'name': name,
                'description': description
            })
