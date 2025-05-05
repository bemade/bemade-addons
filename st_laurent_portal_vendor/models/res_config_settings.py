# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Utilisation de champs many2one pour sélectionner un pays à la fois
    vendor_request_default_country_id = fields.Many2one(
        'res.country',
        string="Pays par défaut",
        config_parameter='st_laurent_portal_vendor.default_country',
        help="Pays par défaut dans le formulaire de demande de vendeur."
    )
    
    vendor_request_restrict_countries = fields.Boolean(
        string="Restreindre les pays disponibles",
        config_parameter='st_laurent_portal_vendor.restrict_countries',
        help="Si activé, seuls les pays spécifiés seront disponibles dans le formulaire de demande de vendeur."
    )
    
    vendor_request_restrict_states = fields.Boolean(
        string="Restreindre les états/provinces disponibles",
        config_parameter='st_laurent_portal_vendor.restrict_states',
        help="Si activé, seuls les états/provinces spécifiés seront disponibles dans le formulaire de demande de vendeur."
    )
    
    # Pays et états autorisés (stockés comme des paramètres de configuration)
    vendor_request_north_america = fields.Boolean(
        string="Amérique du Nord",
        config_parameter='st_laurent_portal_vendor.north_america',
        help="Inclure les pays d'Amérique du Nord (Canada, États-Unis, Mexique)"
    )
    
    vendor_request_europe = fields.Boolean(
        string="Europe",
        config_parameter='st_laurent_portal_vendor.europe',
        help="Inclure les pays d'Europe"
    )
    
    vendor_request_asia = fields.Boolean(
        string="Asie",
        config_parameter='st_laurent_portal_vendor.asia',
        help="Inclure les pays d'Asie"
    )
    
    vendor_request_other_regions = fields.Boolean(
        string="Autres régions",
        config_parameter='st_laurent_portal_vendor.other_regions',
        help="Inclure les pays des autres régions"
    )
    
    @api.model
    def get_allowed_countries(self):
        """Récupère les pays autorisés pour les demandes de vendeur"""
        # Vérifier si la restriction est activée
        restrict = self.env['ir.config_parameter'].sudo().get_param('st_laurent_portal_vendor.restrict_countries', 'false')
        if restrict != 'true':
            return self.env['res.country'].search([])
        
        # Récupérer les régions activées
        regions = []
        if self.env['ir.config_parameter'].sudo().get_param('st_laurent_portal_vendor.north_america', False) == 'true':
            regions.append('north_america')
        if self.env['ir.config_parameter'].sudo().get_param('st_laurent_portal_vendor.europe', False) == 'true':
            regions.append('europe')
        if self.env['ir.config_parameter'].sudo().get_param('st_laurent_portal_vendor.asia', False) == 'true':
            regions.append('asia')
        if self.env['ir.config_parameter'].sudo().get_param('st_laurent_portal_vendor.other_regions', False) == 'true':
            regions.append('other')
        
        # Si aucune région n'est sélectionnée, retourner tous les pays
        if not regions:
            return self.env['res.country'].search([])
        
        # Définir les pays par région
        country_codes = []
        if 'north_america' in regions:
            country_codes.extend(['CA', 'US', 'MX'])
        if 'europe' in regions:
            country_codes.extend(['FR', 'DE', 'GB', 'IT', 'ES', 'PT', 'BE', 'NL', 'LU', 'CH', 'AT', 'SE', 'NO', 'DK', 'FI', 'IE', 'PL'])
        if 'asia' in regions:
            country_codes.extend(['CN', 'JP', 'KR', 'IN', 'SG', 'MY', 'TH', 'VN', 'ID', 'PH'])
        
        # Retourner les pays correspondants aux codes
        if country_codes:
            return self.env['res.country'].search([('code', 'in', country_codes)])
        return self.env['res.country'].search([])
    
    @api.model
    def get_allowed_states(self):
        """Toujours retourner tous les états/provinces pour tous les pays autorisés"""
        countries = self.get_allowed_countries()
        return self.env['res.country.state'].search([('country_id', 'in', countries.ids)])
