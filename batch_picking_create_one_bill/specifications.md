# Spécifications du module batch_picking_create_one_bill

## Objectif
Créer un module Odoo 18.0 permettant de générer une seule facture fournisseur (vendor bill) consolidée pour tous les bons de commande (Purchase Orders) associés à un batch picking, en utilisant la méthode standard de création de factures d'Odoo basée sur les réceptions.

## Fonctionnalités principales

### 1. Modification du comportement des Batch Pickings

#### Héritage du modèle `stock.picking.batch`

##### Champs ajoutés
```python
# Dans stock_picking_batch.py
class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    zero_quantity_default = fields.Boolean(
        string='Quantités à zéro par défaut',
        default=True,
        help='Initialiser les quantités à zéro lors de la création du batch'
    )
    invoice_count = fields.Integer(
        compute='_compute_invoice_count',
        string='Nombre de factures'
    )
    invoice_ids = fields.Many2many(
        'account.move',
        string='Factures associées',
        compute='_compute_invoice_ids',
        store=True
    )
```

##### Surcharge des méthodes

###### Initialisation des quantités
```python
def _prepare_move_line_vals(self, **kwargs):
    vals = super()._prepare_move_line_vals(**kwargs)
    if self.zero_quantity_default:
        vals['quantity'] = 0.0
    return vals
```

###### Calcul des factures associées
```python
@api.depends('picking_ids', 'picking_ids.purchase_id.invoice_ids')
def _compute_invoice_ids(self):
    for batch in self:
        invoices = batch.picking_ids.mapped('purchase_id.invoice_ids')
        batch.invoice_ids = invoices
        batch.invoice_count = len(invoices)
```

##### Actions et boutons
```python
def action_view_invoices(self):
    self.ensure_one()
    action = self.env['ir.actions.act_window']._for_xml_id(
        'account.action_move_in_invoice_type'
    )
    if self.invoice_count == 1:
        action['views'] = [(False, 'form')]
        action['res_id'] = self.invoice_ids.id
    else:
        action['domain'] = [('id', 'in', self.invoice_ids.ids)]
    return action
```

#### Modification des vues

##### Vue formulaire du batch picking
```xml
<record id="view_picking_batch_form_inherit" model="ir.ui.view">
    <field name="name">stock.picking.batch.form.inherit</field>
    <field name="model">stock.picking.batch</field>
    <field name="inherit_id" ref="stock.view_picking_batch_form"/>
    <field name="arch" type="xml">
        <xpath expr="//header" position="inside">
            <button name="%(action_create_batch_bill_wizard)d"
                    string="Créer Facture"
                    type="action"
                    class="btn-primary"
                    attrs="{'invisible': [('state', '!=', 'done')]}"/>
        </xpath>
        <xpath expr="//div[@name='button_box']" position="inside">
            <button class="oe_stat_button"
                    name="action_view_invoices"
                    type="object"
                    icon="fa-pencil-square-o">
                <field name="invoice_count" widget="statinfo" string="Factures"/>
            </button>
        </xpath>
        <xpath expr="//group[@name='group_misc']" position="inside">
            <field name="zero_quantity_default"/>
        </xpath>
    </field>
</record>
```

#### Gestion des mouvements de stock

##### Modification du comportement des move lines
```python
def _update_move_lines_values(self, moves):
    res = super()._update_move_lines_values(moves)
    if self.zero_quantity_default:
        for move in moves:
            for line in move.move_line_ids:
                line.qty_done = 0.0
    return res
```

##### Validation des quantités
```python
def _check_received_quantities(self):
    self.ensure_one()
    for move in self.move_lines:
        if move.quantity_done > move.product_uom_qty:
            raise ValidationError(
                _('La quantité reçue ne peut pas être supérieure '
                  'à la quantité commandée pour le produit %s') 
                % move.product_id.display_name
            )
```

### 2. Critères de regroupement
- Regroupement uniquement des PO du même fournisseur
- Facturation basée uniquement sur les quantités réellement reçues dans le batch picking
- Les lignes de PO non reçues ne seront pas incluses dans la facture

### 2. Processus de création de facture
- Un bouton dédié sera ajouté sur le batch picking après sa validation
- Pour chaque PO du batch :
  1. Utilisation de la méthode standard d'Odoo `action_create_invoice` pour créer les factures basées sur les réceptions
  2. Les factures sont créées selon la politique 'Sur réception' (On received quantities)
  3. Création automatique de factures partielles pour les quantités reçues
- Fusion automatique de toutes les factures créées en une seule facture
  1. Regroupement des lignes par produit
  2. Conservation des liens avec les PO d'origine
  3. Suppression des factures individuelles après fusion

### 3. Gestion des cas particuliers
- Vérification des quantités reçues vs commandées
- Validation que toutes les réceptions sont bien effectuées avant la création de la facture
- Gestion des écarts entre les quantités commandées et reçues

### 4. Sécurité et droits d'accès
- Restriction aux utilisateurs du groupe 'Invoicing user'
- Vérification des droits d'accès sur les documents liés (PO, réceptions)

### 5. Interface utilisateur
- Ajout d'un bouton sur la vue form du batch picking
- Rapports spécifiques pour le suivi des factures groupées [À PRÉCISER]
- Messages de confirmation/erreur clairs pour l'utilisateur

### 6. Aspects techniques
- Pas de règles spécifiques pour la numérotation des factures (utilisation du système standard)
- Intégration avec les modules stock_picking_batch et purchase
- Respect des règles de facturation basées sur les réceptions

## Workflow
1. Création et traitement normal du batch picking
2. Validation du batch picking
3. Utilisation du nouveau bouton pour créer la facture groupée
4. Pour chaque PO impliqué dans le batch picking :
   - Utilisation de la méthode standard `action_create_invoice` d'Odoo
   - Création automatique des factures basées sur les quantités reçues
   - Les quantités non reçues restent en attente de facturation
5. Fusion automatique de toutes les factures créées en une seule facture fournisseur
   - Regroupement des lignes par produit
   - Maintien des références aux PO d'origine
   - Conservation des taxes et comptes analytiques
   - Suppression des factures individuelles après fusion réussie
6. Traitement normal de la facture fusionnée

## Impact sur les processus existants
- Les utilisateurs devront entrer manuellement les quantités reçues au lieu de les ajuster
- Réduction des erreurs de réception dues aux quantités pré-remplies
- Meilleure traçabilité des quantités réellement reçues vs commandées

## Détails techniques d'implémentation

### 1. Modification du comportement des Batch Pickings
- Héritage du modèle `stock.picking.batch`
- Surcharge de la méthode de création pour initialiser les quantités à 0
- Modification des champs de quantité dans `stock.move.line`

### 2. Gestion des factures

#### Wizard de création de facture (`create_merged_bill.py`)

##### 1. Modèles

###### Modèle principal : `batch.picking.create.bill.wizard`
- Champs principaux :
  - `batch_id`: Many2one vers stock.picking.batch (readonly)
    - Batch picking source pour la création de la facture
  - `purchase_order_ids`: Many2many vers purchase.order (computed, readonly)
    - Liste des PO associés au batch
    - Calculé automatiquement depuis le batch
  - `partner_id`: Many2one vers res.partner (computed, readonly)
    - Fournisseur commun à tous les PO
    - Vérification d'unicité du fournisseur
  - `invoice_ids`: Many2many vers account.move (computed)
    - Factures créées par le processus standard d'Odoo
    - Utilisé temporairement avant la fusion
  - `merged_invoice_id`: Many2one vers account.move
    - Facture finale fusionnée
  - `preview_available`: Boolean (computed)
    - Indique si la prévisualisation est possible

###### Modèle temporaire : `batch.picking.create.bill.line.preview`
- Champs :
  - `wizard_id`: Many2one vers le wizard principal
  - `product_id`: Many2one vers product.product
  - `description`: Char (nom du produit + description)
  - `quantity`: Float (quantité reçue)
  - `uom_id`: Many2one vers uom.uom
  - `price_unit`: Float
  - `price_subtotal`: Float
  - `purchase_line_ids`: Many2many vers purchase.order.line
  - `picking_ids`: Many2many vers stock.picking

##### 2. Fonctions principales

###### Calculs et vérifications
- `_compute_purchase_orders()`:
  ```python
  def _compute_purchase_orders(self):
      for wizard in self:
          pickings = wizard.batch_id.picking_ids
          purchase_orders = pickings.mapped('purchase_id')
          wizard.purchase_order_ids = purchase_orders
  ```

- `_compute_partner()`:
  ```python
  def _compute_partner(self):
      for wizard in self:
          partners = wizard.purchase_order_ids.mapped('partner_id')
          if len(partners) != 1:
              raise ValidationError(_('Tous les PO doivent avoir le même fournisseur'))
          wizard.partner_id = partners
  ```

###### Préparation des données
- `_prepare_invoice_lines()`:
  - Regroupe les lignes par produit
  - Calcule les quantités reçues
  - Vérifie la cohérence des prix
  - Génère les lignes de facture

- `_prepare_preview_lines()`:
  - Crée les lignes de prévisualisation
  - Affiche les détails des réceptions
  - Calcule les sous-totaux

###### Actions
- `action_create_bill()`:
  1. Vérifications préalables
  2. Création des factures par PO
  3. Fusion des factures
  4. Liaison avec le batch picking
  5. Retour vers la facture créée

##### 3. Interface utilisateur

###### Vue formulaire principale
```xml
<form>
    <header>
        <button name="action_create_bill" 
                string="Créer Facture" 
                type="object" 
                class="btn-primary" 
                attrs="{'invisible': [('preview_available', '=', False)]}"/>
        <button special="cancel" string="Annuler" class="btn-secondary"/>
    </header>
    <sheet>
        <group>
            <group>
                <field name="batch_id"/>
                <field name="partner_id"/>
                <field name="currency_id"/>
            </group>
            <group>
                <field name="amount_total"/>
                <field name="preview_available" invisible="1"/>
            </group>
        </group>
        <notebook>
            <page string="Ordres d'achat">
                <field name="purchase_order_ids"/>
            </page>
            <page string="Prévisualisation des lignes">
                <field name="preview_line_ids">
                    <tree>
                        <field name="product_id"/>
                        <field name="description"/>
                        <field name="quantity"/>
                        <field name="uom_id"/>
                        <field name="price_unit"/>
                        <field name="price_subtotal"/>
                    </tree>
                </field>
            </page>
        </notebook>
    </sheet>
</form>
```

##### 4. Messages et Validations

###### Messages d'erreur
- Fournisseur différent :
  ```python
  _('Les bons de commande sélectionnés ont des fournisseurs différents : %s')
  ```
- Batch non validé :
  ```python
  _('Le batch picking doit être validé avant de créer la facture')
  ```
- Quantités invalides :
  ```python
  _('Certaines lignes ont des quantités reçues invalides')
  ```

###### Validations automatiques
- Vérification de l'état du batch
- Contrôle des quantités reçues
- Vérification des devises
- Validation des droits d'accès

### 3. Modifications de l'interface

#### Modifications des vues principales

##### 1. Vue formulaire du batch picking (`stock_picking_batch_views.xml`)
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Héritage de la vue form du batch picking -->
    <record id="view_picking_batch_form_inherit" model="ir.ui.view">
        <field name="name">stock.picking.batch.form.inherit</field>
        <field name="model">stock.picking.batch</field>
        <field name="inherit_id" ref="stock.view_picking_batch_form"/>
        <field name="arch" type="xml">
            <!-- Ajout du bouton de création de facture -->
            <xpath expr="//header" position="inside">
                <button name="%(action_create_batch_bill_wizard)d"
                        string="Créer Facture"
                        type="action"
                        class="btn-primary"
                        attrs="{'invisible': [('state', '!=', 'done')]}"/>
            </xpath>
            <!-- Ajout du smart button pour les factures -->
            <div name="button_box" position="inside">
                <button class="oe_stat_button"
                        name="action_view_invoices"
                        type="object"
                        icon="fa-pencil-square-o">
                    <field name="invoice_count" widget="statinfo" string="Factures"/>
                </button>
            </div>
            <!-- Ajout de l'option quantités à zéro -->
            <group name="group_misc" position="inside">
                <field name="zero_quantity_default"/>
            </group>
        </field>
    </record>

    <!-- Vue tree des batch pickings -->
    <record id="view_picking_batch_tree_inherit" model="ir.ui.view">
        <field name="name">stock.picking.batch.tree.inherit</field>
        <field name="model">stock.picking.batch</field>
        <field name="inherit_id" ref="stock.view_picking_batch_tree"/>
        <field name="arch" type="xml">
            <field name="state" position="after">
                <field name="invoice_count"/>
            </field>
        </field>
    </record>

    <!-- Vue search des batch pickings -->
    <record id="view_picking_batch_search_inherit" model="ir.ui.view">
        <field name="name">stock.picking.batch.search.inherit</field>
        <field name="model">stock.picking.batch</field>
        <field name="inherit_id" ref="stock.view_picking_batch_search"/>
        <field name="arch" type="xml">
            <filter name="to_process" position="after">
                <filter string="Non facturé"
                        name="not_invoiced"
                        domain="[('invoice_count', '=', 0)]"/>
                <filter string="Facturé"
                        name="invoiced"
                        domain="[('invoice_count', '>', 0)]"/>
            </filter>
        </field>
    </record>
</odoo>
```

##### 2. Vue formulaire de la facture (`account_move_views.xml`)
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_move_form_inherit" model="ir.ui.view">
        <field name="name">account.move.form.inherit</field>
        <field name="model">account.move</field>
        <field name="inherit_id" ref="account.view_move_form"/>
        <field name="arch" type="xml">
            <!-- Ajout des références aux batch pickings -->
            <xpath expr="//field[@name='invoice_origin']" position="after">
                <field name="batch_picking_ids"
                       widget="many2many_tags"
                       readonly="1"
                       attrs="{'invisible': [('move_type', '!=', 'in_invoice')]}"/>
            </xpath>
        </field>
    </record>
</odoo>
```

#### Actions et menus

##### Actions du wizard
```xml
<record id="action_create_batch_bill_wizard" model="ir.actions.act_window">
    <field name="name">Créer Facture Fournisseur</field>
    <field name="res_model">batch.picking.create.bill.wizard</field>
    <field name="view_mode">form</field>
    <field name="target">new</field>
    <field name="binding_model_id" ref="model_stock_picking_batch"/>
    <field name="binding_view_types">form</field>
</record>
```

#### Sécurité et droits d'accès

##### Groupes et droits
```xml
<record id="group_batch_invoice" model="res.groups">
    <field name="name">Création de factures depuis batch picking</field>
    <field name="category_id" ref="base.module_category_inventory"/>
    <field name="implied_ids" eval="[(4, ref('account.group_account_invoice'))]"/>
</record>
```

##### Règles d'accès
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_batch_bill_wizard,access.batch.picking.create.bill.wizard,model_batch_picking_create_bill_wizard,group_batch_invoice,1,1,1,0
access_batch_bill_line_preview,access.batch.picking.create.bill.line.preview,model_batch_picking_create_bill_line_preview,group_batch_invoice,1,1,1,1
```

### 4. Points techniques clés

#### Manifest du module
```python
{
    'name': 'Batch Picking - Create One Bill',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Purchase',
    'summary': 'Créer une seule facture pour tous les PO d’un batch picking',
    'author': 'Pneumac',
    'website': 'https://www.pneumac.com',
    'license': 'LGPL-3',
    'depends': [
        'stock_picking_batch',
        'purchase',
        'account',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/stock_picking_batch_views.xml',
        'views/account_move_views.xml',
        'wizard/create_merged_bill_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
```

#### Structure complète des fichiers
```
batch_picking_create_one_bill/
├── __init__.py                      # Import des sous-modules
├── __manifest__.py                  # Configuration du module
├── models/                         # Définition des modèles
│   ├── __init__.py
│   ├── stock_picking_batch.py      # Extension du modèle batch
│   └── account_move.py            # Extension du modèle facture
├── wizard/                         # Assistant de création de facture
│   ├── __init__.py
│   ├── create_merged_bill.py       # Logique du wizard
│   └── create_merged_bill_views.xml # Vues du wizard
├── views/                          # Vues des modèles
│   ├── stock_picking_batch_views.xml
│   └── account_move_views.xml
├── security/                       # Sécurité et droits d'accès
│   ├── ir.model.access.csv         # Règles d'accès aux modèles
│   └── security_groups.xml         # Définition des groupes
├── static/                        # Ressources statiques
│   └── description/
│       └── icon.png                # Icône du module
└── i18n/                          # Traductions
    └── fr.po                       # Traduction française

```

#### Points techniques spécifiques

##### 1. Gestion des hooks
```python
# Dans stock_picking_batch.py
from odoo import models, fields, api, _

class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    @api.model
    def create(self, vals):
        # Hook de création pour initialiser les quantités à 0
        res = super().create(vals)
        if res.zero_quantity_default:
            res._reset_quantities()
        return res

    def write(self, vals):
        # Hook d'écriture pour gérer les modifications
        res = super().write(vals)
        if 'zero_quantity_default' in vals:
            self._handle_quantity_change()
        return res
```

##### 2. Gestion des contraintes
```python
@api.constrains('picking_ids', 'picking_ids.purchase_id')
def _check_purchase_orders(self):
    for batch in self:
        purchases = batch.picking_ids.mapped('purchase_id')
        partners = purchases.mapped('partner_id')
        if len(partners) > 1:
            raise ValidationError(_(
                'Le batch picking ne peut contenir que des PO '
                'du même fournisseur.'
            ))
```

##### 3. Performance et optimisation
```python
# Dans create_merged_bill.py
from odoo.tools.profiler import profile

@profile
def _prepare_invoice_lines(self):
    # Optimisation avec prefetch
    products = self.env['product.product'].browse(
        self.purchase_order_ids.mapped('order_line.product_id.id')
    ).exists()
    products.read(['name', 'type', 'invoice_policy'])

    # Traitement par lots
    moves_by_product = {}
    for move in self.batch_id.move_lines:
        if move.product_id not in moves_by_product:
            moves_by_product[move.product_id] = self.env['stock.move']
        moves_by_product[move.product_id] |= move
```

##### 4. Gestion des erreurs
```python
class BatchBillError(Exception):
    """ Erreur spécifique pour la création de facture depuis batch """
    pass

def _handle_bill_creation_error(self, error):
    if isinstance(error, BatchBillError):
        # Erreur métier spécifique
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Erreur'),
                'message': str(error),
                'type': 'danger',
            }
        }
    # Autres erreurs
    raise error
```

##### 5. Tests unitaires
```python
# Dans tests/test_batch_bill.py
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

@tagged('post_install', '-at_install')
class TestBatchBill(TransactionCase):

    def setUp(self):
        super().setUp()
        # Préparation des données de test

    def test_create_bill_from_batch(self):
        # Test de création de facture

    def test_zero_quantity_default(self):
        # Test de l'initialisation des quantités

    def test_merge_bills(self):
        # Test de la fusion des factures
```
- Gestion des états des documents (draft, done, etc.)
- Traçabilité complète via les champs related et stored
- Gestion des droits d'accès via les groupes de sécurité

### 5. Améliorations suggérées

#### 1. Fonctionnalités supplémentaires
- **Annulation en masse** :
  - Possibilité d'annuler la facture créée et de revenir à l'état précédent
  - Traçabilité des annulations dans l'historique

- **Rapports et analyses** :
  - Rapport de réconciliation PO/Réceptions/Factures

#### 2. Améliorations techniques
- **Cache et performance** :
  - Mise en cache des calculs fréquents
  - Optimisation des requêtes SQL
  - Indexation des champs clés

- **Gestion des erreurs avancée** :
  - Journal d'erreurs détaillé
  - Mécanisme de reprise sur erreur
  - Notifications utilisateur améliorées

- **Tests automatisés** :
  - Tests d'intégration avec scénarios complexes
  - Tests de performance
  - Tests de régression

#### 3. Améliorations UX
- **Interface utilisateur** :
  - Vue kanban pour les batch pickings avec statut de facturation
  - Filtres et groupements avancés
  - Aperçu rapide des informations clés

- **Processus utilisateur** :
  - Assistant de validation en plusieurs étapes
  - Suggestions automatiques basées sur l'historique
  - Messages d'aide contextuels

#### 4. Personnalisation
- **Configuration avancée** :
  - Paramètres par entreprise

### 5. Structure des fichiers
```
batch_picking_create_one_bill/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── stock_picking_batch.py
│   └── account_move.py
├── wizard/
│   ├── __init__.py
│   └── create_merged_bill.py
├── views/
│   ├── stock_picking_batch_views.xml
│   └── account_move_views.xml
├── security/
│   └── ir.model.access.csv
└── data/
    └── security_groups.xml
```

## Dépendances
- stock_picking_batch
- purchase
- account

## Version
- Odoo 18.0
