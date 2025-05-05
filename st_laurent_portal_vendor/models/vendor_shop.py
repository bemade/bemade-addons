from odoo import models, fields, api

class VendorShop(models.Model):
    _name = 'vendor.shop'
    _description = 'Boutique Vendeur'
    _sql_constraints = [
        ('slug_unique', 'unique(slug)', "L'URL de la boutique doit être unique.")
    ]

    name = fields.Char('Nom de la boutique', required=True)
    slug = fields.Char('Slug URL', required=True, help="Utilisé pour l'URL /shop/slug")
    vendor_id = fields.Many2one('res.partner', string='Vendeur', required=True, domain=[('is_company', '=', True)])
    product_ids = fields.One2many('product.template', 'vendor_shop_id', string='Produits')

    @api.model
    def create_shop_for_vendor(self, vendor):
        # Génère un slug unique basé sur le nom du vendeur
        slug = vendor.name.lower().replace(' ', '-')
        existing = self.search([('slug', '=', slug)])
        if existing:
            slug = f"{slug}-{vendor.id}"
        return self.create({
            'name': vendor.name,
            'slug': slug,
            'vendor_id': vendor.id,
        })

# Extension du modèle product.template
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    vendor_shop_id = fields.Many2one('vendor.shop', string='Boutique du vendeur')
