# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.tools.image import is_image_size_above
from odoo.exceptions import UserError


class VendorProduct(models.Model):
    _inherit = 'vendor.product'
    _description = 'Produit vendeur avec fonctionnalités e-commerce'
    
    # Champ de base pour l'archivage
    active = fields.Boolean('Actif', default=True, tracking=True)

    # Champs d'image (repris de vendor_product_image)
    image_1920 = fields.Image("Image", max_width=1920, max_height=1920, attachment=True)
    image_1024 = fields.Image("Image 1024", related="image_1920", max_width=1024, max_height=1024, store=True)
    image_512 = fields.Image("Image 512", related="image_1920", max_width=512, max_height=512, store=True)
    image_256 = fields.Image("Image 256", related="image_1920", max_width=256, max_height=256, store=True)
    image_128 = fields.Image("Image 128", related="image_1920", max_width=128, max_height=128, store=True)
    can_image_1024_be_zoomed = fields.Boolean("Can Image 1024 be zoomed", compute='_compute_can_image_1024_be_zoomed', store=True)
    
    # Champs e-commerce de base
    website_published = fields.Boolean('Publié sur le site web', default=False, copy=False)
    website_description = fields.Html('Description du site web', translate=True, sanitize_attributes=False)
    website_url = fields.Char('URL du site web', compute='_compute_website_url')
    
    # Catégories et tags
    public_categ_ids = fields.Many2many(
        'product.public.category', string='Catégories du site web',
        help="Les catégories pour l'affichage sur le site web")
    product_tag_ids = fields.Many2many(
        'product.tag', string='Tags',
        help="Tags pour le filtrage et la catégorisation")
        
    # Prix et disponibilité
    website_price = fields.Float('Prix sur le site web', digits='Product Price')
    website_ribbon = fields.Char('Ruban du site web', help="Texte affiché dans un ruban sur le produit (ex: 'Nouveau', 'Promotion')")
    availability = fields.Selection([
        ('in_stock', 'En stock'),
        ('out_of_stock', 'Épuisé'),
        ('preorder', 'Précommande'),
        ('discontinued', 'Abandonné')
    ], string='Disponibilité', default='in_stock')
    availability_date = fields.Date('Date de disponibilité')
    
    # SEO et métadonnées
    website_meta_title = fields.Char('Titre Meta', translate=True)
    website_meta_description = fields.Text('Description Meta', translate=True)
    website_meta_keywords = fields.Char('Mots-clés Meta', translate=True)
    website_meta_og_img = fields.Binary('Image Open Graph')
    
    # Autres informations utiles
    barcode = fields.Char('Code-barres', copy=False)
    default_code = fields.Char('Référence interne', copy=False)
    website_sequence = fields.Integer('Séquence sur le site web', default=50, help="Détermine l'ordre d'affichage sur le site web")
    
    # Champs pour les messages de succès/erreur
    success = fields.Char(string="Message de succès", readonly=True, copy=False)
    error = fields.Char(string="Message d'erreur", readonly=True, copy=False)
    
    # Champs manquants nécessaires pour le fonctionnement du module
    partner_id = fields.Many2one('res.partner', string='Partenaire', tracking=True)
    product_name = fields.Char('Nom du produit', required=True, tracking=True)
    product_code = fields.Char('Code produit', tracking=True)
    description = fields.Text('Description', tracking=True)
    product_tmpl_id = fields.Many2one('product.template', string='Produit associé', copy=False)
    product_id = fields.Many2one('product.product', string='Variante de produit', copy=False)
    
    # Gestion des quantités
    vendor_quantity = fields.Float('Quantité disponible', default=0.0, tracking=True)
    zero_qty = fields.Float('Quantité nulle', compute='_compute_zero_qty', store=True)
    
    # Prix
    price = fields.Float('Prix', digits='Product Price', default=0.0, tracking=True)
    
    # Champs pour la synchronisation avec product.product
    commission_rate = fields.Float('Taux de commission (%)', default=10.0)
    auto_sync_price = fields.Boolean('Synchronisation auto. des prix', default=True)
    auto_sync_images = fields.Boolean('Synchronisation auto. des images', default=True)
    last_sync_date = fields.Datetime('Dernière synchronisation', readonly=True)
    
    # Champs pour l'historique des prix
    old_price = fields.Float('Ancien prix', digits='Product Price', readonly=True)
    price_change_date = fields.Datetime('Date changement prix', readonly=True)
    price_change_user_id = fields.Many2one('res.users', string='Modifié par', readonly=True)
    final_price = fields.Float(string='Montant net vendeur', compute='_compute_final_price', digits='Product Price', help='Montant que le vendeur recevra après déduction de la commission')

    @api.depends('image_1920', 'image_1024')
    def _compute_can_image_1024_be_zoomed(self):
        for record in self:
            record.can_image_1024_be_zoomed = record.image_1920 and is_image_size_above(record.image_1920, record.image_1024)
            
    @api.depends('vendor_quantity')
    def _compute_zero_qty(self):
        for record in self:
            record.zero_qty = 1.0 if record.vendor_quantity <= 0 else 0.0
            
    @api.depends('price', 'commission_rate')
    def _compute_final_price(self):
        """Calcule le prix net pour le vendeur après commission"""
        for record in self:
            # Le prix final est le montant que le vendeur recevra après déduction de la commission
            record.final_price = record.price * (1 - record.commission_rate / 100)
            
    @api.onchange('price')
    def _onchange_price(self):
        """Avertissement lors d'un changement de prix"""
        if self.price and self.old_price and self.price != self.old_price:
            # Calcul du montant net que le vendeur recevra après commission
            net_price = self.price * (1 - self.commission_rate / 100)
            old_net_price = self.old_price * (1 - self.commission_rate / 100)
            return {
                'warning': {
                    'title': _('Changement de prix'),
                    'message': _(
                        'Le prix de vente va changer de %.2f à %.2f.\n'
                        'Votre rémunération (après commission de %.1f%%) passera de %.2f à %.2f.\n'
                        'Si vous confirmez, ce changement sera propagé au produit standard associé.'
                    ) % (self.old_price, self.price, self.commission_rate, old_net_price, net_price)
                }
            }

    def _compute_website_url(self):
        for product in self:
            product.website_url = f'/shop/vendor-product/{product.id}'
            
    def action_publish_website(self):
        self.ensure_one()
        self.website_published = True
        return True
        
    def action_unpublish_website(self):
        self.ensure_one()
        self.website_published = False
        return True
        
    def write(self, vals):
        """Surcharge pour gérer les changements de prix et la synchronisation"""
        # Enregistrement des anciennes valeurs pour l'historique
        for record in self:
            if 'price' in vals and record.price != vals['price']:
                record.old_price = record.price
                record.price_change_date = fields.Datetime.now()
                record.price_change_user_id = self.env.user.id
        
        result = super(VendorProduct, self).write(vals)
        
        # Synchronisation avec le produit standard si nécessaire
        for record in self:
            if record.product_tmpl_id:
                sync_vals = {}
                
                # Synchronisation du prix si modifié et auto-sync activé
                if 'price' in vals and record.auto_sync_price:
                    # Le prix de vente est directement le prix entré par le vendeur
                    sync_vals['list_price'] = record.price
                
                # Synchronisation des images si modifiées et auto-sync activé
                if 'image_1920' in vals and record.auto_sync_images:
                    sync_vals['image_1920'] = record.image_1920
                
                # Mise à jour du produit standard si des valeurs à synchroniser
                if sync_vals:
                    record.product_tmpl_id.write(sync_vals)
                    record.last_sync_date = fields.Datetime.now()
        
        return result

    def action_create_product(self):
        """Créer un produit standard (product.product) à partir du produit vendeur"""
        self.ensure_one()
        ProductTemplate = self.env['product.template']
        
        # Vérifier si un produit existe déjà avec le même code
        existing_product = ProductTemplate.search([('default_code', '=', self.default_code)], limit=1)
        if existing_product:
            # Si un produit existe déjà, afficher un message d'avertissement
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Produit existant',
                    'message': f'Un produit avec la référence {self.default_code} existe déjà.',
                    'sticky': False,
                    'type': 'warning',
                }
            }
        
        # Le prix de vente est directement le prix entré par le vendeur
        # La commission sera retenue lors du paiement au vendeur
        final_price = self.price  # Utiliser directement le prix du vendeur
        
        # Créer le produit
        vals = {
            'name': self.product_name,
            'default_code': self.default_code,
            'barcode': self.barcode,
            'description': self.description,
            'description_sale': self.website_description,
            'list_price': final_price,  # Utilisation du prix avec commission
            'standard_price': self.price,  # Prix d'achat = prix du vendeur sans commission
            'image_1920': self.image_1920,
            'type': 'consu',  # Consommable (valeur par défaut sécuritaire)
            'sale_ok': True,
            'purchase_ok': True,
            'invoice_policy': 'order',
            'purchase_method': 'purchase',
            'categ_id': self.env.ref('product.product_category_all').id,
            'taxes_id': [(6, 0, [])],  # Pas de taxes par défaut
            'supplier_taxes_id': [(6, 0, [])],  # Pas de taxes fournisseur par défaut
        }
        
        # Ajouter les métadonnées SEO si disponibles
        if self.website_meta_title:
            vals['website_meta_title'] = self.website_meta_title
        if self.website_meta_description:
            vals['website_meta_description'] = self.website_meta_description
        if self.website_meta_keywords:
            vals['website_meta_keywords'] = self.website_meta_keywords
        
        # Créer le template de produit
        product_tmpl = ProductTemplate.create(vals)
        
        # Ajouter le fournisseur
        if self.partner_id:
            self.env['product.supplierinfo'].create({
                'product_tmpl_id': product_tmpl.id,
                'partner_id': self.partner_id.id,
                'product_name': self.product_name,
                'product_code': self.product_code,
                'min_qty': 1.0,
                'price': self.price,
            })
        
        # Lier le produit vendeur au produit standard
        self.write({
            'product_tmpl_id': product_tmpl.id,
            'last_sync_date': fields.Datetime.now(),
            'success': f'Produit {product_tmpl.name} créé avec succès!'
        })
        
        # Rediriger vers le produit créé
        return {
            'type': 'ir.actions.act_window',
            'name': 'Produit créé',
            'res_model': 'product.template',
            'res_id': product_tmpl.id,
            'view_mode': 'form',
            'target': 'current',
        }
        
    def sync_to_product(self):
        """Synchronise manuellement toutes les données vers le produit standard"""
        self.ensure_one()
        
        if not self.product_tmpl_id:
            raise UserError(_('Ce produit vendeur n\'est pas lié à un produit standard.'))
        
        # Le prix de vente est directement le prix entré par le vendeur
        # La commission sera retenue lors du paiement au vendeur
        final_price = self.price  # Utiliser directement le prix du vendeur
        
        # Préparation des valeurs à synchroniser
        vals = {
            'name': self.product_name,
            'description': self.description,
            'description_sale': self.website_description,
            'list_price': final_price,
            'standard_price': self.price,  # Prix d'achat = prix du vendeur sans commission
            'default_code': self.default_code,
            'barcode': self.barcode,
        }
        
        # Ajout de l'image si disponible
        if self.image_1920:
            vals['image_1920'] = self.image_1920
        
        # Mise à jour du produit standard
        self.product_tmpl_id.write(vals)
        
        # Mise à jour de la date de synchronisation
        self.write({
            'last_sync_date': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Synchronisation réussie'),
                'message': _('Le produit a été synchronisé avec succès.'),
                'sticky': False,
                'type': 'success',
            }
        }
