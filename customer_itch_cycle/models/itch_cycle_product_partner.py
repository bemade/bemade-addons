from datetime import datetime, timedelta
import numpy as np
from odoo import models, fields, api
from odoo.exceptions import UserError


class ItchCycleProductPartner(models.Model):
    _name = "itch.cycle.product.partner"
    _description = "Cycle Produit/Partenaire"

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Client",
        required=True
    )

    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Produit",
        required=True
    )

    quantity_total_ordered = fields.Float(
        string="Quantité totale commandée",
        compute="_compute_quantity_total_ordered",
        store=True
    )

    quantity_of_orders = fields.Integer(
        string="Nombre de commandes",
        compute="_compute_quantity_of_orders",
        store=True
    )

    min_quantity_ordered = fields.Float(
        string="Quantité minimale commandée",
        compute="_compute_min_quantity_ordered",
        store=True
    )

    max_quantity_ordered = fields.Float(
        string="Quantité maximale commandée",
        compute="_compute_max_quantity_ordered",
        store=True
    )

    mean_quantity_ordered = fields.Float(
        string="Quantité moyenne commandée",
        compute="_compute_mean_quantity_ordered",
        store=True
    )

    average_cycle = fields.Integer(
        string="Cycle moyen (jours)",
        compute="_compute_average_cycle",
        store=True
    )

    manualy_set_cycle = fields.Integer(
        string="Cycle moyen (jours) défini manuellement"
    )

    manualy_set_qty = fields.Float(
        string="Quantité défini manuellement"
    )

    next_expected_date = fields.Date(
        string="Prochaine vente prévue",
        compute="_compute_next_expected_date",
        store=True
    )

    manualy_set_next_date = fields.Date(
        string="Prochaine vente prévue défini manuellement"
    )

    calc_next_date = fields.Date(
        string="Prochaine vente prévue calculée",
        compute="_compute_next_expected_date",
        store=True
    )

    calc_average_cycle = fields.Integer(
        string="Cycle moyen (jours) calculé",
        compute="_compute_itch_cycle_duration",
        store=True
    )

    calc_average_qty = fields.Float(
        string="Quantité moyenne calculée",
        compute="_compute_mean_quantity_ordered",
        store=True
    )

    @api.depends('manualy_set_cycle','average_cycle')
    def _compute_itch_cycle_duration(self):
        for record in self:
            if record.manualy_set_cycle:
                record.calc_average_cycle = record.manualy_set_cycle
            else:
                record.calc_average_cycle = record.average_cycle

    @api.depends('manualy_set_qty','max_quantity_ordered')
    def _compute_mean_quantity_ordered(self):
        for record in self:
            if record.manualy_set_qty:
                record.calc_average_qty = record.manualy_set_qty
            else:
                record.calc_average_qty = record.max_quantity

    prediction_status = fields.Selection(
        selection=[
            ('on_time', 'À l’heure'),
            ('delayed', 'Retardée')
        ],
        string="Statut de la prédiction",
        compute="_compute_prediction_status"
    )

    sale_order_line_ids = fields.One2many(
        comodel_name='sale.order.line',
        inverse_name='itch_cycle_id',
        string="Lignes de commande"
    )

    next_follow_up_date = fields.Date(
        string="Prochaine date de suivi",
        compute="_compute_next_follow_up_date",
        store=True,
        readonly=False
    )

    last_purchase_date = fields.Date(
        string="Date du dernier achat",
        compute="_compute_last_purchase_date",
        store=True
    )

    itch_cycle_duration = fields.Integer(
        string="Durée du cycle (jours)",
        help="Représente la durée moyenne du cycle en jours",
        compute="_compute_itch_cycle_duration",
        store=True
    )

    @api.depends('average_cycle')
    def _compute_itch_cycle_duration(self):
        """Calcule automatiquement la durée du cycle."""
        for record in self:
            record.itch_cycle_duration = record.average_cycle or 0

    @api.depends('sale_order_line_ids')
    def _compute_last_purchase_date(self):
        """Met automatiquement à jour la date du dernier achat."""
        for record in self:
            # Rechercher la commande la plus récente associée
            last_order = record.sale_order_line_ids.mapped('order_id').sorted(key=lambda o: o.date_order, reverse=True)
            record.last_purchase_date = last_order[0].date_order if last_order else None

    @api.depends('next_expected_date')
    def _compute_next_follow_up_date(self):
        """
           Définit la logique pour calculer automatiquement la date de suivi.
           Peut être basée sur `next_expected_date`, mais modifiable par l'utilisateur.
           """
        for record in self:
            if record.next_expected_date:
                # Exemple : une alerte de suivi une semaine avant la prochaine vente prévue
                record.next_follow_up_date = record.next_expected_date - timedelta(days=7)
            else:
                record.next_follow_up_date = None

    @api.depends('sale_order_line_ids', 'product_id.categ_id')
    def _compute_average_cycle(self):
        for record in self:
            product_category = record.product_id.categ_id
            if product_category.seasonal_factor and product_category.season_months:
                # Filtrer les commandes par mois saisonniers de la catégorie
                active_months = list(map(int, product_category.season_months.split(',')))
                dates = sorted([
                    line.order_id.date_order
                    for line in record.sale_order_line_ids
                    if line.order_id.date_order.month in active_months
                ])
            else:
                # Cycle habituel (non saisonnier)
                dates = sorted(record.sale_order_line_ids.mapped('order_id.date_order'))

            if len(dates) > 1:
                intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
                record.average_cycle = int(np.mean(intervals)) if intervals else 0
            else:
                record.average_cycle = 0

    @api.depends('average_cycle')
    def _compute_next_expected_date(self):
        for record in self:
            if record.average_cycle and record.sale_order_line_ids:
                last_date = max(record.sale_order_line_ids.mapped('order_id.date_order'))
                record.next_expected_date = fields.Date.from_string(last_date) + timedelta(days=record.average_cycle)
            else:
                record.next_expected_date = None

    def _compute_prediction_status(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.next_expected_date and record.next_expected_date < today:
                record.prediction_status = 'delayed'
            else:
                record.prediction_status = 'on_time'

    @api.model
    def populate_from_past_orders(self):
        """
        Méthode pour traiter le passé :
        Crée des enregistrements 'itch.cycle.product.partner'
        basés sur les commandes de vente existantes.
        """
        # Récupérer toutes les lignes de commandes confirmées
        sale_order_lines = self.env['sale.order.line'].search([
            ('order_id.state', 'in', ['sale', 'done']),  # Commandes confirmées ou terminées
            ('qty_delivered', '>', 0),  # Quantité livrée supérieure à 0
            ('product_id', '!=', False)  # Exclure les lignes sans produit
#            ('order_id.partner_id', '=', 5024659),  # un client pour test
        ])

        # Carte pour regrouper par couple (client, produit)
        cycle_data = {}

        for line in sale_order_lines:
            key = (line.order_id.partner_id.id, line.product_id.id)
            if key not in cycle_data:
                cycle_data[key] = {
                    'partner_id': line.order_id.partner_id.id,
                    'product_id': line.product_id.id,
                    'sale_order_line_ids': []
                }
            cycle_data[key]['sale_order_line_ids'].append(line.id)  # Ajouter l'ID de la ligne

        # Créer les enregistrements manquants dans Itch Cycle
        for key, data in cycle_data.items():
            partner_id, product_id = key

            # Vérifier si l'enregistrement existe déjà
            itch_cycle = self.search([('partner_id', '=', partner_id), ('product_id', '=', product_id)], limit=1)

            if not itch_cycle:
                # Calculer le cycle moyen basé sur les dates de commandes
                order_dates = sorted([self.env['sale.order.line'].browse(line_id).order_id.date_order
                                      for line_id in data['sale_order_line_ids']])
                if len(order_dates) > 1:
                    intervals = [(order_dates[i + 1] - order_dates[i]).days for i in range(len(order_dates) - 1)]
                    average_cycle = sum(intervals) // len(intervals) if intervals else 0
                else:
                    average_cycle = 0

                # Créer l'enregistrement dans la table Itch Cycle
                if product_id and partner_id:
                    self.create({
                        'partner_id': partner_id,
                        'product_id': product_id,
                        'sale_order_line_ids': [(6, 0, data['sale_order_line_ids'])]
                    })
                else:
                    #raise UserError("Impossible de créer un cycle sans client ou produit associé.")
                    print("Impossible de créer un cycle sans client ou produit associé.")
                    print('valeur de product_id', product_id)
                    print('valeur de partner_id', partner_id)
            else:
                # Mettre à jour les lignes de commande si nécessaire
                itch_cycle.write({
                    'sale_order_line_ids': [(6, 0, data['sale_order_line_ids'])],  # Lier ou actualiser les lignes
                })
        return True

    @api.depends('sale_order_line_ids')
    def _compute_quantity_total_ordered(self):
        for record in self:
            record.quantity_total_ordered = sum(record.sale_order_line_ids.mapped('product_uom_qty'))

    @api.depends('sale_order_line_ids')
    def _compute_quantity_of_orders(self):
        for record in self:
            record.quantity_of_orders = len(record.sale_order_line_ids)

    @api.depends('sale_order_line_ids')
    def _compute_min_quantity_ordered(self):
        for record in self:
            record.min_quantity_ordered = min(record.sale_order_line_ids.mapped('product_uom_qty'))

    @api.depends('sale_order_line_ids')
    def _compute_max_quantity_ordered(self):
        for record in self:
            record.max_quantity_ordered = max(record.sale_order_line_ids.mapped('product_uom_qty'))

    @api.depends('sale_order_line_ids')
    def _compute_mean_quantity_ordered(self):
        for record in self:
            record.mean_quantity_ordered = np.mean(record.sale_order_line_ids.mapped('product_uom_qty'))
