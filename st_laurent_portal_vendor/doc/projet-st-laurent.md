# Projet St-Laurent
## Une fédération e-commerce québécoise basée sur Odoo

---

## Sommaire exécutif

Le projet St-Laurent vise à créer une alternative québécoise à Amazon suite à la fermeture du Panier Bleu, en développant une fédération de plateformes e-commerce basées sur Odoo 18.0. Cette architecture à trois niveaux permettra aux entreprises québécoises de vendre leurs produits en ligne avec une commission exceptionnellement basse de 2%, positionnant St-Laurent comme la solution la plus économique et la plus adaptée au contexte québécois.

La fédération St-Laurent s'articule autour de trois niveaux complémentaires :

1. **Odoo Enterprise Local** (régional/municipal) : Permettant aux micro-entreprises d'accéder facilement à une boutique en ligne via une interface simplifiée de type portal user.

2. **Odoo Enterprise Central** (provincial) : Agrégeant l'ensemble des Odoo régionaux pour offrir une expérience d'achat unifiée aux consommateurs à travers tout le Québec.

3. **Odoo ERP Commerçant** (Community ou Enterprise) : Offrant aux entreprises une solution complète de gestion intégrée à l'écosystème St-Laurent, avec un choix de rayonnement local ou provincial.

St-Laurent deviendra partenaire officiel Odoo pour le Québec, avec l'objectif explicite d'accompagner les entreprises dans leur migration vers Odoo Enterprise 18.0, générant ainsi un modèle d'affaires à triple valeur ajoutée : les plateformes e-commerce régionales, la plateforme provinciale unifiée, et les services d'intégration Odoo.

---

## Vision et objectifs

### Vision
Devenir la première destination en ligne pour l'achat de produits québécois, en offrant une alternative locale, économique et technologiquement avancée aux géants du commerce électronique international, tout en respectant les spécificités régionales à travers une architecture fédérée.

### Objectifs
1. Créer un écosystème e-commerce québécois autonome, décentralisé et compétitif
2. Proposer la commission la plus basse du marché (2%)
3. Simplifier la présence en ligne des entreprises québécoises de toutes tailles
4. Fédérer les acteurs économiques locaux à travers une structure régionale et provinciale
5. Offrir une évolution progressive des solutions, du simple portal user à l'ERP complet
6. Valoriser les identités régionales tout en offrant une visibilité provinciale
7. Faciliter l'intégration complète pour les utilisateurs d'Odoo Enterprise et Community

---

## Architecture technique

### 1. Architecture à trois niveaux

#### Niveau 1: Odoo Enterprise Local (Régional/Municipal)
- **Base**: Odoo Enterprise Edition 18.0
- **Objectif**: Fournir une micro-boutique en ligne pour les vendeurs locaux
- **Modules principaux**:
  - Website (base)
  - E-commerce
  - Paiement en ligne
  - Gestion des contacts simplifiée
- **Modules personnalisés**:
  - **st_laurent_local_core**: Fonctionnalités de base de la plateforme locale
    - Personnalisation régionale (identité visuelle, contenu local)
    - Configuration des règles de marketplace locale
    - Administration des vendeurs locaux
  - **st_laurent_portal_vendor**: Interface simplifiée pour utilisateurs portal
    - Inscription et création autonome de compte vendeur
    - Formulaires simplifiés d'ajout de produits
    - Gestion des commandes par vendeur
    - Notifications et alertes
  - **st_laurent_federation_client**: Connecteur vers l'Odoo Central
    - Synchronisation des produits vers la plateforme centrale
    - Réception des commandes de la plateforme centrale
    - Statut de synchronisation et diagnostics

#### Niveau 2: Odoo Enterprise Central (Provincial)
- **Base**: Odoo Enterprise Edition 18.0
- **Objectif**: Agréger tous les Odoo régionaux et offrir une expérience unifiée
- **Modules principaux**:
  - Website (base)
  - E-commerce avancé
  - Paiement en ligne multi-méthodes
  - CRM
  - Marketing automation
  - Voicemail
  - Signature électronique
- **Modules personnalisés**:
  - **st_laurent_central_core**: Fonctionnalités de la plateforme centrale
    - Gestion du modèle de commission (2%)
    - Administration centralisée de la fédération
    - Tableaux de bord provinciaux
  - **st_laurent_federation_server**: Gestion de la fédération
    - Enregistrement et gestion des instances régionales
    - Routage intelligent des commandes
    - Synchronisation et indexation des produits
    - Monitoring de santé de la fédération
  - **st_laurent_marketplace**: Gestion multi-vendeurs et multi-régions
    - Ventilation des commandes multi-vendeurs
    - Système de messagerie vendeur-client-admin
    - Gestion des avis et évaluations
    - Outils de recherche et filtrage avancés
    - Comparaison de produits inter-régions

#### Niveau 3: Odoo ERP Commerçant (Community ou Enterprise)
- **Base**: Odoo Community Edition 18.0 ou Enterprise Edition 18.0 (au choix)
- **Objectif**: Fournir une solution ERP complète aux commerçants
- **Modules principaux**: Tous les modules standards Odoo selon les besoins
  - Inventaire
  - Comptabilité
  - Achats
  - Ventes
  - Fabrication
  - RH
  - etc.
- **Modules personnalisés**:
  - **st_laurent_connector**: Connecteur vers les plateformes St-Laurent
    - Synchronisation bidirectionnelle
    - Mapping flexible des champs et modèles
    - Choix du rayonnement (local ou provincial)
    - Gestion des erreurs et conflits
    - Tableau de bord de santé des connecteurs

### 2. Infrastructure serveur

#### Hébergement fédéré
- **Niveau 1 (Local)**: Serveurs régionaux (possibilité d'hébergement par partenaires locaux)
- **Niveau 2 (Central)**: Infrastructure cloud québécoise haute disponibilité (OVH, CloudWatt)
- **Niveau 3 (Commerçant)**: Au choix du commerçant (on-premise ou cloud)

#### Architecture technique
- **Fédération**: Architecture distribuée avec registre central
- **Isolation**: Multi-tenant avec isolation des données par région
- **Scaling**: Auto-scaling basé sur la charge (niveau central)
- **Redondance**: Configuration active-passive avec basculement automatique
- **Sauvegarde**: Quotidienne avec rétention de 30 jours

### 3. Interfaces utilisateur

#### Frontend client (Niveau 1 et 2)
- **Design**: Interface adaptée à l'identité québécoise avec déclinaisons régionales
- **Responsivité**: Mobile-first approach
- **Multilingue**: Français et anglais
- **Personnalisation**: Thème St-Laurent avec variantes régionales
- **Performance**: Optimisation SEO et vitesse de chargement

#### Backend vendeur
- **Niveau 1**: Interface portal simplifiée pour micro-entreprises
- **Niveau 2**: Dashboard provincial avec vue globale
- **Niveau 3**: Interface Odoo standard avec connecteurs St-Laurent

### 4. Système de connecteurs

#### Connecteurs inter-niveaux
- **Protocole**: API REST bidirectionnelle sécurisée
- **Authentification**: OAuth2 avec clés API
- **Synchronisation**:
  - Produits et catalogues (Local → Central)
  - Commandes (Central → Local)
  - Inventaire en temps réel
  - Prix et promotions

#### API externe
- **Documentation**: Spécifications OpenAPI
- **Endpoints standardisés** pour tous les niveaux:
  - /products: Gestion des produits
  - /orders: Gestion des commandes
  - /inventory: Mise à jour des stocks
  - /webhooks: Notifications événementielles
  - /federation: Gestion de la fédération (niveau 2 uniquement)

---

## Fonctionnalités principales

### 1. Niveau 1: Odoo Enterprise Local (Régional/Municipal)

#### Gestion des vendeurs locaux
- Processus d'inscription simplifié pour micro-entreprises locales
- Vérification d'éligibilité (entreprises de la région/ville)
- Tutoriel interactif d'intégration pour utilisateurs non-techniques
- Configuration guidée du profil vendeur local

#### Interface portal vendeur
- Vue d'ensemble simplifiée des ventes et performances
- Alertes et notifications essentielles
- Gestion basique des produits et commandes
- Interface adaptée aux utilisateurs non-techniques

#### Gestion des produits
- Formulaires simplifiés d'ajout de produits
- Support pour attributs et variantes de base
- Gestion des images (multi-vues)
- Mise en avant de l'origine locale des produits

#### Gestion des commandes locales
- Notifications de nouvelles commandes
- Processus simplifié de traitement des commandes
- Suivi de livraison basique
- Support client de proximité

### 2. Niveau 2: Odoo Enterprise Central (Provincial)

#### Fédération des plateformes régionales
- Agrégation des produits de toutes les instances régionales
- Recherche unifiée à travers toutes les régions
- Filtrage par région, distance, disponibilité
- Mise en avant des spécificités régionales

#### Expérience d'achat unifiée
- Panier d'achat multi-régions
- Processus de commande unifié
- Paiement centralisé (Stripe, PayPal, Desjardins)
- Suivi de commandes multi-vendeurs

#### Gestion des commandes provinciales
1. Client passe commande sur la plateforme centrale
2. Paiement traité par la plateforme centrale
3. Commande ventilée vers les plateformes régionales concernées
4. Confirmation de traitement par chaque vendeur régional
5. Suivi de livraison consolidé pour le client

#### Marketing et promotion provinciale
- Campagnes marketing à l'échelle du Québec
- Mise en avant des produits régionaux
- Programmes de fidélité provinciaux
- Événements promotionnels saisonniers

#### Administration centrale
- Tableau de bord de la fédération
- Monitoring de santé des instances régionales
- Rapports consolidés de ventes et performances
- Gestion des commissions (2% standard)

### 3. Niveau 3: Odoo ERP Commerçant (Community ou Enterprise)

#### Intégration complète
- Synchronisation bidirectionnelle avec les plateformes St-Laurent
- Choix du rayonnement (local ou provincial)
- Gestion avancée des produits et variantes
- Automatisation des flux de travail

#### Fonctionnalités ERP complètes
- Gestion d'inventaire avancée
- Comptabilité intégrée
- CRM et gestion de la relation client
- Fabrication et gestion de production
- Ressources humaines
- Point de vente physique

#### Tableau de bord vendeur avancé
- Analyse détaillée des ventes par canal
- Prévisions et tendances
- KPIs personnalisables
- Business intelligence

#### Gestion multi-canal
- Intégration St-Laurent (local et/ou provincial)
- Possibilité d'intégration avec d'autres marketplaces
- Synchronisation avec boutique physique
- Gestion omnicanal complète

### 4. Fonctionnalités transversales

#### Paiement et facturation
- Paiement centralisé au niveau provincial
- Commission de 2% retenue automatiquement
- Transfert des fonds aux vendeurs (délai J+3)
- Facturation mensuelle des services additionnels

#### Service client multi-niveau
- Support de proximité au niveau régional
- Support centralisé pour questions transversales
- Système d'évaluation des vendeurs harmonisé
- Centre d'aide et FAQ à chaque niveau

#### Identité et personnalisation
- Thème commun St-Laurent avec déclinaisons régionales
- Personnalisation des boutiques vendeurs
- Badges et certifications (produits locaux, artisanaux, etc.)
- Mise en avant des spécificités culturelles régionales

---

## Modèle économique

### 1. Structure de revenus

#### Commission base
- **Taux fixe**: 2% sur toutes les ventes (niveau provincial)
- **Positionnement**: Le plus bas du marché

#### Services additionnels par niveau
- **Niveau 1 (Local)**: 
  - Visibilité locale premium (25-100$/mois)
  - Support technique de proximité (tarifs variables selon régions)

- **Niveau 2 (Provincial)**:
  - Visibilité premium en page d'accueil provinciale (50-200$/mois)
  - Outils marketing avancés: Campagnes email, analytics avancées (30-100$/mois)
  - Mise en avant dans les résultats de recherche provinciaux (tarifs variables)

- **Niveau 3 (ERP Commerçant)**:
  - Services d'implémentation et personnalisation Odoo
  - Formation et support technique
  - Développements spécifiques
  - Migration depuis d'autres systèmes
- **Support dédié**: Assistance prioritaire (25$/mois)
- **Formation**: Sessions personnalisées (75$/heure)

#### Partenariat Odoo
- **Statut de partenaire officiel Odoo** pour le Québec
- Commissions sur nouveaux déploiements Odoo Enterprise (15-25% des contrats)
- Services d'intégration et personnalisation à valeur ajoutée
- Formation et support Odoo certifiés
- Stratégie de migration proactive des vendeurs vers Odoo Enterprise
- Développement de modules verticaux spécifiques aux industries québécoises

### 2. Structure de coûts

#### Développement initial
- Développement plateforme: 200 000$ - 300 000$
- Design et UX: 50 000$ - 75 000$
- Tests et assurance qualité: 25 000$ - 50 000$

#### Opérations continues
- Infrastructure cloud: 5 000$ - 10 000$/mois
- Support technique: 10 000$ - 15 000$/mois
- Marketing et acquisition: 10 000$ - 20 000$/mois
- Équipe produit: 20 000$ - 40 000$/mois

#### Mise à l'échelle
- Prévision d'investissement par palier de 1000 vendeurs
- Réserve opérationnelle de 6 mois minimum

---

## Modifications techniques Odoo 18.0 Enterprise

### 1. Extension portal user pour création de comptes et gestion produits

```python
# Modèle de sécurité étendu (st_laurent_portal_vendor/security/ir.model.access.csv)
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_product_template_sl_vendor,product.template.sl.vendor,product.model_product_template,st_laurent_portal_vendor.group_sl_vendor,1,1,1,0
access_product_product_sl_vendor,product.product.sl.vendor,product.model_product_product,st_laurent_portal_vendor.group_sl_vendor,1,1,1,0
access_product_image_sl_vendor,product.image.sl.vendor,product.model_product_image,st_laurent_portal_vendor.group_sl_vendor,1,1,1,1
access_product_attribute_sl_vendor,product.attribute.sl.vendor,product.model_product_attribute,st_laurent_portal_vendor.group_sl_vendor,1,1,0,0
access_product_attribute_value_sl_vendor,product.attribute.value.sl.vendor,product.model_product_attribute_value,st_laurent_portal_vendor.group_sl_vendor,1,1,1,0
access_product_category_sl_vendor,product.category.sl.vendor,product.model_product_category,st_laurent_portal_vendor.group_sl_vendor,1,0,0,0
```

```python
# Modèle étendu de partenaire pour gestion vendeur
class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    is_st_laurent_vendor = fields.Boolean('Vendeur St-Laurent', default=False)
    vendor_status = fields.Selection([
        ('pending', 'En attente d\'approbation'),
        ('approved', 'Approuvé'),
        ('suspended', 'Suspendu')
    ], string='Statut vendeur', default='pending')
    vendor_commission_rate = fields.Float('Taux de commission', default=2.0)
    vendor_category_ids = fields.Many2many('product.public.category', string='Catégories autorisées')
    vendor_products_count = fields.Integer('Nombre de produits', compute='_compute_vendor_products_count')
    vendor_sales_count = fields.Integer('Nombre de ventes', compute='_compute_vendor_sales_count')
    vendor_registration_date = fields.Datetime('Date d\'inscription vendeur')
    vendor_description = fields.Html('Description boutique')
    
    # Méthodes de calcul et validation...
```

```python
# Règle de sécurité avancée pour isolation multi-vendeurs
class ProductTemplateVendorRule(models.Model):
    _name = 'st_laurent.product.template.rule'
    _description = 'Règle de sécurité pour produits vendeur'
    
    @api.model
    def _apply_ir_rules(self, query, mode='read'):
        if self.env.user.has_group('st_laurent_portal_vendor.group_sl_vendor'):
            # Accès limité aux produits du vendeur uniquement
            query.where_clause += ["product_template.vendor_id = %s"]
            query.where_clause_params += [self.env.user.partner_id.id]
            
            # Restrictions additionnelles selon statut vendeur
            partner = self.env.user.partner_id
            if partner.vendor_status != 'approved':
                # Vendeur en attente ou suspendu - lecture seule
                if mode in ('write', 'create', 'unlink'):
                    query.where_clause += ["1=0"]  # Bloquer toute modification
        return super()._apply_ir_rules(query, mode)
```

### 2. Interface portail vendeur avancée

```python
# Contrôleur web complet pour portail vendeur avec auto-inscription
class StLaurentVendorPortal(PortalController):
    @http.route(['/vendor/register'], type='http', auth="public", website=True)
    def vendor_register(self, **kw):
        """Page d'inscription vendeur accessible sans connexion"""
        return request.render("st_laurent_portal_vendor.vendor_register_form")
    
    @http.route(['/vendor/register/submit'], type='http', auth="public", website=True, methods=['POST'])
    def vendor_register_submit(self, **kw):
        """Traitement inscription vendeur et création compte portal"""
        # Validation des données
        required_fields = ['name', 'email', 'company_name', 'phone', 'business_number']
        for field in required_fields:
            if not kw.get(field):
                return request.render("st_laurent_portal_vendor.vendor_register_form", {
                    'error': f"Le champ {field} est obligatoire",
                    'data': kw
                })
        
        # Vérification email unique
        if request.env['res.partner'].sudo().search([('email', '=', kw.get('email'))]):
            return request.render("st_laurent_portal_vendor.vendor_register_form", {
                'error': "Cet email est déjà utilisé",
                'data': kw
            })
            
        # Création du partenaire
        vendor_data = {
            'name': kw.get('company_name'),
            'email': kw.get('email'),
            'phone': kw.get('phone'),
            'is_company': True,
            'is_st_laurent_vendor': True,
            'vendor_status': 'pending',
            'vendor_registration_date': fields.Datetime.now(),
            'vendor_description': kw.get('description', ''),
            'company_id': request.website.company_id.id,
        }
        
        partner = request.env['res.partner'].sudo().create(vendor_data)
        
        # Création utilisateur portal
        user_data = {
            'name': kw.get('name'),
            'login': kw.get('email'),
            'partner_id': partner.id,
            'groups_id': [(6, 0, [
                request.env.ref('base.group_portal').id,
                request.env.ref('st_laurent_portal_vendor.group_sl_vendor').id
            ])]
        }
        
        # Générer mot de passe aléatoire et envoyer par email
        user = request.env['res.users'].sudo().create(user_data)
        user.action_reset_password()
        
        # Notification administrateurs
        admin_users = request.env['res.users'].sudo().search([
            ('groups_id', 'in', request.env.ref('st_laurent_core.group_sl_admin').id)
        ])
        request.env['mail.mail'].sudo().create({
            'subject': f"Nouvelle inscription vendeur: {partner.name}",
            'body_html': f"""
                <p>Un nouveau vendeur s'est inscrit sur la plateforme St-Laurent:</p>
                <ul>
                    <li>Entreprise: {partner.name}</li>
                    <li>Contact: {user.name}</li>
                    <li>Email: {user.login}</li>
                </ul>
                <p>Veuillez vérifier et approuver ce vendeur dans l'administration.</p>
            """,
            'email_to': ','.join(admin_users.mapped('email')),
            'auto_delete': True,
        }).send()
        
        return request.render("st_laurent_portal_vendor.vendor_register_success")

    @http.route(['/vendor/dashboard'], type='http', auth="user", website=True)
    def vendor_dashboard(self, **kw):
        """Tableau de bord principal vendeur"""
        if not request.env.user.partner_id.is_st_laurent_vendor:
            return request.redirect('/')
            
        partner = request.env.user.partner_id
        products = request.env['product.template'].search([
            ('vendor_id', '=', partner.id)
        ])
        
        # Statistiques
        sales_data = self._get_vendor_sales_data(partner)
        
        values = {
            'partner': partner,
            'products_count': len(products),
            'pending_orders': sales_data['pending_count'],
            'monthly_sales': sales_data['monthly_total'],
            'status': partner.vendor_status,
        }
        
        return request.render("st_laurent_portal_vendor.vendor_dashboard", values)
    
    @http.route(['/vendor/products'], type='http', auth="user", website=True)
    def vendor_products(self, **kw):
        """Liste des produits du vendeur avec gestion"""
        if not request.env.user.partner_id.is_st_laurent_vendor:
            return request.redirect('/')
            
        products = request.env['product.template'].search([
            ('vendor_id', '=', request.env.user.partner_id.id)
        ])
        
        values = {
            'products': products,
            'categories': request.env['product.public.category'].search([]),
        }
        
        return request.render("st_laurent_portal_vendor.vendor_products", values)
    
    @http.route(['/vendor/product/new', '/vendor/product/<int:product_id>/edit'], type='http', auth="user", website=True)
    def vendor_product_form(self, product_id=None, **kw):
        """Formulaire création/édition produit pour vendeurs portal"""
        if not request.env.user.partner_id.is_st_laurent_vendor:
            return request.redirect('/')
            
        product = False
        if product_id:
            product = request.env['product.template'].browse(product_id)
            # Vérification propriétaire
            if product.vendor_id.id != request.env.user.partner_id.id:
                return request.redirect('/vendor/products')
        
        # Récupération des catégories et attributs autorisés
        categories = request.env['product.public.category'].search([])
        attributes = request.env['product.attribute'].search([])
        
        values = {
            'product': product,
            'categories': categories,
            'attributes': attributes,
            'error': {},
            'partner': request.env.user.partner_id,
        }
        
        return request.render("st_laurent_portal_vendor.vendor_product_form", values)
        
    @http.route(['/vendor/product/save'], type='http', auth="user", website=True, methods=['POST'])
    def vendor_product_save(self, **kw):
        """Traitement sauvegarde produit vendeur"""
        if not request.env.user.partner_id.is_st_laurent_vendor:
            return request.redirect('/')
            
        # Logique de validation et sauvegarde du produit...
        # (code détaillé pour validation, création images, attributs, etc.)
        
        return request.redirect('/vendor/products')
```

### 3. Connecteur avancé Odoo 18.0 à Odoo 18.0 Enterprise

```python
# Module connecteur complet avec support de toutes les fonctionnalités Odoo 18.0
class StLaurentOdooConnector(models.Model):
    _name = 'st_laurent.odoo.connector'
    _description = 'Connecteur St-Laurent Odoo à Odoo Enterprise'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Nom du connecteur', required=True)
    vendor_id = fields.Many2one('res.partner', string='Vendeur', required=True, domain=[('is_st_laurent_vendor', '=', True)])
    api_key = fields.Char('Clé API', readonly=True, copy=False)
    url_endpoint = fields.Char('URL de l\'instance Odoo', required=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('test', 'Test de connexion'),
        ('ready', 'Prêt'),
        ('active', 'Actif'),
        ('error', 'Erreur'),
        ('disabled', 'Désactivé')
    ], string='État', default='draft', tracking=True)
    
    # Options de synchronisation
    sync_products = fields.Boolean('Synchroniser produits', default=True)
    sync_inventory = fields.Boolean('Synchroniser inventaire', default=True)
    sync_orders = fields.Boolean('Synchroniser commandes', default=True)
    sync_customers = fields.Boolean('Synchroniser clients', default=False)
    
    # Paramètres avancés
    sync_interval = fields.Integer('Intervalle (minutes)', default=15, help="Intervalle de synchronisation automatique")
    webhook_url = fields.Char('URL Webhook', compute='_compute_webhook_url', readonly=True)
    webhook_token = fields.Char('Token Webhook', readonly=True, copy=False)
    log_level = fields.Selection([
        ('debug', 'Debug - Tous les détails'),
        ('info', 'Info - Événements importants'),
        ('warning', 'Warning - Erreurs non critiques'),
        ('error', 'Error - Erreurs critiques uniquement')
    ], string='Niveau de log', default='info')
    
    # Statistiques
    last_sync = fields.Datetime('Dernière synchronisation', readonly=True)
    last_sync_status = fields.Selection([
        ('success', 'Succès'),
        ('partial', 'Succès partiel'),
        ('failed', 'Échec')
    ], string='Statut dernière sync', readonly=True)
    sync_count = fields.Integer('Nombre de synchronisations', readonly=True, default=0)
    error_count = fields.Integer('Nombre d\'erreurs', readonly=True, default=0)
    product_count = fields.Integer('Produits synchronisés', readonly=True, default=0)
    error_message = fields.Text('Message d\'erreur', readonly=True)
    
    # Journal d'activité
    log_ids = fields.One2many('st_laurent.connector.log', 'connector_id', string='Journal de synchronisation')
    
    # Mapping des champs
    field_mapping_ids = fields.One2many('st_laurent.connector.field.mapping', 'connector_id', string='Mapping des champs')
    
    @api.model
    def create(self, vals):
        """Génération de clés sécurisées à la création"""
        vals['api_key'] = self._generate_secure_key(64)
        vals['webhook_token'] = self._generate_secure_key(32)
        return super().create(vals)
    
    def _generate_secure_key(self, length):
        """Génère une clé sécurisée aléatoire"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def _compute_webhook_url(self):
        """Calcule l'URL de webhook pour ce connecteur"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            record.webhook_url = f"{base_url}/st_laurent/webhook/{record.id}/{record.webhook_token}"
    
    def action_test_connection(self):
        """Test de connexion à l'instance Odoo du vendeur"""
        self.ensure_one()
        try:
            # Configuration de la connexion
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            # Requête simple pour vérifier la connexion
            response = requests.get(
                f"{self.url_endpoint}/api/v1/version",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            # Vérification version Odoo
            version_info = response.json()
            if not version_info.get('version', '').startswith('18.'):
                raise ValidationError("L'instance distante n'est pas en version Odoo 18")
                
            self.write({
                'state': 'ready',
                'error_message': False
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connexion réussie',
                    'message': f"Connexion établie avec l'instance Odoo {version_info.get('version')}",
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erreur de connexion',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_sync_now(self):
        """Déclenche une synchronisation manuelle complète"""
        self.ensure_one()
        if self.state not in ['ready', 'active', 'error']:
            raise UserError("Le connecteur n'est pas prêt pour la synchronisation")
        
        # Démarrage synchronisation dans une tâche asynchrone
        self.env['st_laurent.connector.job'].create({
            'connector_id': self.id,
            'job_type': 'full_sync',
            'state': 'pending'
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Synchronisation lancée',
                'message': "La synchronisation a été programmée et sera exécutée en arrière-plan",
                'type': 'info',
                'sticky': False,
            }
        }
    
    def sync_products(self):
        """Synchronise les produits depuis l'Odoo du vendeur"""
        self.ensure_one()
        
        # Préparation du log de synchronisation
        sync_log = self.env['st_laurent.connector.log'].create({
            'connector_id': self.id,
            'operation': 'sync_products',
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Configuration de la connexion
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            # Récupération de la date de dernière synchronisation pour sync incrémentale
            last_sync_date = self.last_sync or fields.Datetime.subtract(fields.Datetime.now(), days=30)
            last_sync_str = fields.Datetime.to_string(last_sync_date)
            
            # Paramètres de pagination
            page = 1
            per_page = 50
            total_synced = 0
            has_more = True
            
            while has_more:
                # Requête paginée pour les produits modifiés depuis la dernière sync
                response = requests.get(
                    f"{self.url_endpoint}/api/v1/products",
                    headers=headers,
                    params={
                        'modified_since': last_sync_str,
                        'page': page,
                        'per_page': per_page
                    },
                    timeout=60
                )
                response.raise_for_status()
                
                data = response.json()
                products_data = data.get('data', [])
                
                if not products_data:
                    has_more = False
                    continue
                
                # Traitement par lots de produits
                for product_data in products_data:
                    result = self._process_vendor_product(product_data)
                    if result.get('success'):
                        total_synced += 1
                    
                    # Logging détaillé en mode debug
                    if self.log_level == 'debug':
                        sync_log.add_detail(
                            product_id=product_data.get('id'),
                            status='success' if result.get('success') else 'error',
                            message=result.get('message', '')
                        )
                
                # Pagination
                page += 1
                has_more = data.get('has_more', False)
            
            # Mise à jour des statistiques
            self.write({
                'last_sync': fields.Datetime.now(),
                'last_sync_status': 'success',
                'sync_count': self.sync_count + 1,
                'product_count': self.product_count + total_synced,
            })
            
            # Finalisation du log
            sync_log.write({
                'end_time': fields.Datetime.now(),
                'status': 'success',
                'message': f"Synchronisation réussie de {total_synced} produits"
            })
            
            return {
                'status': 'success',
                'count': total_synce

---

## Feuille de route du projet

### Phase 1: Développement initial - Pilote régional (4 mois)
- Étude des besoins et spécifications détaillées
- Développement du core de la plateforme
- Construction de l'interface vendeur portail
- Tests utilisateurs avec panel d'entreprises québécoises

### Phase 2: MVP et lancement pilote (3 mois)
- Sélection de 20-30 vendeurs pilotes
- Déploiement en environnement de production
- Optimisation des processus
- Premier connecteur Odoo-à-Odoo

### Phase 3: Lancement public (3 mois)
- Campagne marketing de lancement
- Onboarding des premiers 100 vendeurs
- Développement des fonctionnalités additionnelles
- Optimisation de la performance

### Phase 4: Croissance et expansion (12+ mois)
- Élargissement de la base vendeurs
- Développement de l'application mobile
- Intégration de nouveaux services
- Expansion potentielle au-delà du Québec

---

## Stratégie marketing

### 1. Positionnement
- **Slogan proposé**: "St-Laurent, l'avenir du commerce québécois"
- **Proposition de valeur**: La plateforme e-commerce la plus économique pour les entreprises québécoises
- **Différenciateurs clés**:
  - Commission fixe de 2% (vs. 15% moyenne Amazon)
  - 100% québécois
  - Intégration native avec Odoo Enterprise

### 2. Stratégie d'acquisition vendeurs
- Partenariats avec associations d'entreprises québécoises
- Webinaires et événements de présentation
- Programme de référencement (prime pour recommandation)
- Campagne ciblée sur les vendeurs Amazon/Shopify existants

### 3. Stratégie d'acquisition clients
- Mise en avant du "Fait au Québec"
- Campagnes de sensibilisation économie locale
- Partenariats influenceurs québécois
- Stratégie SEO/SEM locale

---

## Gouvernance et organisation

### Structure proposée
- Entreprise à but lucratif avec mission sociale
- Conseil d'administration incluant des représentants des vendeurs
- Comité consultatif avec acteurs économiques québécois

### Équipe initiale
- Direction générale (1)
- Développement technique (4-6)
- Expérience utilisateur (2)
- Acquisition vendeurs (2-3)
- Support client (2-4)
- Marketing (2)

---

## Analyse des risques

### 1. Risques techniques
- **Intégration Odoo complexe**: Mitigation par phase de tests extensifs
- **Scalabilité plateforme**: Architecture cloud évolutive
- **Sécurité données**: Audits réguliers et conformité RGPD/PIPEDA

### 2. Risques commerciaux
- **Adoption limitée**: Stratégie d'acquisition aggressive et commission ultra-basse
- **Rétention vendeurs**: Services à valeur ajoutée et support premium
- **Concurrence future**: Premier entrant avec avantage établi

### 3. Risques financiers
- **Viabilité modèle 2%**: Diversification revenus et services additionnels
- **Coûts infrastructure**: Optimisation continue et scaling progressif
- **Délai rentabilité**: Plan financier sur 3 ans avec objectifs précis

---

## Conclusion

Le projet St-Laurent représente une opportunité unique de créer une infrastructure e-commerce nationale pour le Québec, en s'appuyant sur la puissance et la flexibilité d'Odoo. Avec sa commission disruptive de 2%, la plateforme offre un avantage compétitif significatif aux entreprises québécoises face aux géants internationaux.

L'approche technique proposée, combinant une plateforme centrale et des connecteurs Odoo-à-Odoo avancés, permet d'offrir une solution flexible qui s'adapte aux besoins variés des entreprises, des plus petits artisans aux plus grandes entreprises utilisant déjà Odoo Enterprise.

St-Laurent a le potentiel de devenir le carrefour incontournable du commerce électronique québécois, stimulant l'économie locale tout en offrant une alternative viable et économique aux plateformes dominantes.

---

## Annexes

### Annexe A: Glossaire technique
### Annexe B: Comparatif détaillé des commissions
### Annexe C: Maquettes d'interface
### Annexe D: Architecture technique détaillée
### Annexe E: Plan financier prévisionnel

---

*Document confidentiel - Projet St-Laurent - Avril 2025*
