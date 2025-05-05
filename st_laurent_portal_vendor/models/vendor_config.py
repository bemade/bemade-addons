# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class VendorConfig(models.Model):
    _name = 'vendor.config'
    _description = 'Configuration des paramètres vendeur'

    name = fields.Char(string="Nom", required=True, default="Configuration par défaut")
    active = fields.Boolean(string="Actif", default=True)
    
    # Pays autorisés
    country_ids = fields.Many2many(
        'res.country',
        string="Pays autorisés",
        help="Pays autorisés dans le formulaire de demande de vendeur. Si vide, tous les pays sont autorisés."
    )
    
    # États/provinces autorisés
    state_ids = fields.Many2many(
        'res.country.state',
        string="États/Provinces autorisés",
        help="États/Provinces autorisés dans le formulaire de demande de vendeur. Si vide, tous les états sont autorisés."
    )
    
    # Champ pour définir cette configuration comme la configuration par défaut
    is_default = fields.Boolean(
        string="Configuration par défaut",
        default=False,
        help="Si coché, cette configuration sera utilisée comme configuration par défaut."
    )
    
    @api.model
    def get_default_config(self):
        """Récupère la configuration par défaut"""
        default_config = self.search([('is_default', '=', True)], limit=1)
        if not default_config:
            default_config = self.search([], limit=1)
        return default_config
    
    @api.model_create_multi
    def create(self, vals_list):
        """Assure qu'il n'y a qu'une seule configuration par défaut"""
        for vals in vals_list:
            if vals.get('is_default'):
                self.search([('is_default', '=', True)]).write({'is_default': False})
        return super(VendorConfig, self).create(vals_list)
    
    def write(self, vals):
        """Assure qu'il n'y a qu'une seule configuration par défaut"""
        if vals.get('is_default'):
            self.search([('is_default', '=', True), ('id', '!=', self.id)]).write({'is_default': False})
        return super(VendorConfig, self).write(vals)
    
    def get_allowed_countries(self):
        """Récupère les pays autorisés"""
        self.ensure_one()
        if not self.country_ids:
            return self.env['res.country'].search([])
        return self.country_ids
    
    def get_allowed_states(self):
        """Récupère les états/provinces autorisés"""
        self.ensure_one()
        if not self.state_ids:
            return self.env['res.country.state'].search([])
        return self.state_ids
