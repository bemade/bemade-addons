# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UdmDnsConfig(models.Model):
    """Configuration DNS pour le système UniFi
    
    Ce modèle stocke la configuration DNS pour les contrôleurs UDM/UDR.
    Il gère les paramètres DNS comme les serveurs personnalisés et le filtrage de contenu.
    
    La configuration DNS est liée à un site spécifique et est automatiquement supprimée
    lorsque le site est supprimé (cascade).
    """
    _name = 'udm.dns.config'
    _description = 'UniFi DNS Configuration'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True,
                             ondelete='cascade',
                             help='Site this DNS configuration belongs to')
    enabled = fields.Boolean(string='Enabled', default=True,
                           help='Enable DNS server')
    filters_enabled = fields.Boolean(string='Content Filtering Enabled', default=False,
                                   help='Enable DNS content filtering')
    custom_dns = fields.Char(string='Custom DNS Servers',
                           help='Comma-separated list of custom DNS servers')
    raw_data = fields.Text(string='Raw Data',
                          help='Raw DNS configuration data in JSON format')
