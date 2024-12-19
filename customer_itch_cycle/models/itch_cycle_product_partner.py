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
        help="Client associé à ce cycle",
        required=True
    )

    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Produit",
        help="Produit associé à ce cycle",
        required=True
    )

    sale_order_line_ids = fields.One2many(
        comodel_name='sale.order.line',
        inverse_name='itch_cycle_id',
        help="Lignes de commande",
        string="Lignes de commande"
    )

    # Quantités: La plus part des champs sont informatifs et calculés automatiquement

    quantity_total_ordered = fields.Float(
        string="Quantité totale commandée",
        compute="_compute_sale_order_line_related_fields",
        help="Quantité totale commandée par le client pour ce produit",
        store=True
    )

    quantity_of_orders = fields.Integer(
        string="Nombre de commandes",
        compute="_compute_sale_order_line_related_fields",
        help="Nombre de commandes passées par le client pour ce produit",
        store=True
    )

    quantity_min_ordered = fields.Float(
        string="Quantité minimale commandée",
        compute="_compute_sale_order_line_related_fields",
        help="Quantité minimale commandée par le client pour ce produit",
        store=True
    )

    quantity_max_ordered = fields.Float(
        string="Quantité maximale commandée",
        compute="_compute_sale_order_line_related_fields",
        help="Quantité maximale commandée par le client pour ce produit",
        store=True
    )

    quantity_mean_ordered = fields.Float(
        string="Quantité moyenne commandée",
        compute="_compute_sale_order_line_related_fields",
        help="Quantité moyenne commandée par le client pour ce produit",
        store=True
    )

    quantity_manual_override = fields.Float(
        string="Quantité défini manuellement",
        help="Quantité défini manuellement"
    )

    quantity_planned = fields.Float(
        string="Quantité prévue",
        help="Quantité prévue pour la prochaine commande",
        compute="_compute_quantity_planned",
        store=True
    )

    # Cycles: La plupart des champs sont informatifs et calculés automatiquement

    cycle_duration_calculated = fields.Integer(
        string="Cycle moyen (jours) calculé",
        compute="_compute_average_cycle",
        help="Cycle moyen calculé en jours",
        store=True
    )

    cycle_duration_override = fields.Integer(
        string="Cycle moyen (jours) défini manuellement",
        help="Cycle moyen défini manuellement en jours"
    )

    cycle_duration = fields.Integer(
        string="Cycle moyen (jours)",
        compute="_compute_itch_cycle_duration",
        help="Cycle moyen en jours",
        store=True
    )

    # Dates:

    date_expected_evaluated = fields.Date(
        string="Prochaine vente prévue par calcul",
        compute="_compute_next_expected_date",
        store=True
    )

    date_next_override = fields.Date(
        string="Prochaine vente prévue défini manuellement",
        help="Prochaine vente prévue défini manuellement"
    )

    date_expected = fields.Date(
        string="Prochaine vente prévue",
        compute="_compute_next_expected_date",
        help="Prochaine vente prévue calculée",
        store=True
    )

    date_next_follow_up = fields.Date(
        string="Prochaine date de suivi",
        compute="_compute_next_follow_up_date",
        help="Prochaine date de suivi",
        store=True,
        readonly=False
    )

    date_last_purchase = fields.Date(
        string="Date du dernier achat",
        compute="_compute_last_purchase_date",
        help="Date du dernier achat",
        store=True
    )

    prediction_status = fields.Selection(
        selection=[
            ('on_time', 'À l’heure'),
            ('delayed', 'Retardée'),
            ('archived', 'Archivée')
        ],
        string="Statut de la prédiction",
        help="Statut de la prédiction",
        compute="_compute_prediction_status"
    )

    @api.depends('cycle_duration_override', 'cycle_duration_calculated')
    def _compute_itch_cycle_duration(self):
        """
        Calcule automatiquement la durée du cycle.
        Si un cycle est défini manuellement, il est utilisé à la place.
        Sinon, le cycle moyen calculé est utilisé.
        """
        for record in self:
            if record.cycle_duration_override:
                record.cycle_duration = record.cycle_duration_override
            else:
                record.cycle_duration = record.cycle_duration_calculated

    @api.depends('quantity_manual_override', 'quantity_max_ordered')
    def _compute_mean_quantity_ordered(self):
        """
        Calcule la quantité de la prochaine commande.
        Si une quantité est définie manuellement, elle est utilisée sinon la quantité maximale est utilisée.
        """
        for record in self:
            if record.quantity_manual_override:
                record.calc_average_qty = record.quantity_manual_override
            else:
                record.calc_average_qty = record.quantity_max_ordered

    @api.depends('sale_order_line_ids')
    def _compute_last_purchase_date(self):
        """
        Met automatiquement à jour la date du dernier achat.
        """
        for record in self:
            # Rechercher la commande la plus récente associée
            last_order = record.sale_order_line_ids.mapped('order_id').sorted(key=lambda o: o.date_order, reverse=True)
            record.date_last_purchase = last_order[0].date_order if last_order else None

    @api.depends('date_expected')
    def _compute_next_follow_up_date(self):
        """
        Définit la logique pour calculer automatiquement la date de suivi.
        Peut être basée sur `next_expected_date`, mais modifiable par l'utilisateur.
        """
        for record in self:
            if record.date_expected:
                # Exemple : une alerte de suivi une semaine avant la prochaine vente prévue
                record.date_next_follow_up = record.date_expected - timedelta(days=7)
            else:
                record.date_next_follow_up = None

    @api.depends('sale_order_line_ids', 'product_id.categ_id')
    def _compute_average_cycle(self):
        """
        Calcule le cycle moyen en jours.
        """
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
                record.cycle_duration_calculated = int(np.mean(intervals)) if intervals else 0
            else:
                record.cycle_duration_calculated = 0

    @api.depends('cycle_duration')
    def _compute_next_expected_date(self):
        """
        Calcule automatiquement la prochaine date de vente
        """
        for record in self:
            if record.cycle_duration and record.sale_order_line_ids:
                last_date = max(record.sale_order_line_ids.mapped('order_id.date_order'))
                record.date_expected_evaluated = fields.Date.from_string(last_date) + timedelta(days=record.cycle_duration)
            else:
                record.date_expected_evaluated = None

    def _compute_prediction_status(self):
        """
        Calcule le statut de la prédiction.
        """
        today = fields.Date.context_today(self)
        for record in self:
            if record.prediction_status == 'archived':
                record.prediction_status = 'archived'
            elif record.date_expected and record.date_expected < today:
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
                    raise UserError('Impossible de créer un cycle sans client ou produit associé.')
                    print('Impossible de créer un cycle sans client ou produit associé.')
                    print('valeur de product_id', product_id)
                    print('valeur de partner_id', partner_id)
            else:
                # Mettre à jour les lignes de commande si nécessaire
                itch_cycle.write({
                    'sale_order_line_ids': [(6, 0, data['sale_order_line_ids'])],  # Lier ou actualiser les lignes
                })
        return True

    @api.depends('sale_order_line_ids')
    def _compute_sale_order_line_related_fields(self):
        """
        Regroupe tous les calculs relatifs aux `sale.order.line`.
        Calcule les statistiques principales : quantité totale, moyenne, minimum, maximum, etc.
        """
        for record in self:
            # Récupérer toutes les quantités des lignes de commande
            quantities = record.sale_order_line_ids.mapped('product_uom_qty')

            # Quantité totale
            record.quantity_total_ordered = sum(quantities)

            # Nombre de commandes (lignes individuelles)
            record.quantity_of_orders = len(record.sale_order_line_ids)

            # Quantité minimale, maximale et moyenne
            if quantities:
                record.quantity_min_ordered = min(quantities)
                record.quantity_max_ordered = max(quantities)
                record.quantity_mean_ordered = np.mean(quantities)
            else:
                record.quantity_min_ordered = 0
                record.quantity_max_ordered = 0
                record.quantity_mean_ordered = 0

            # Dernière date d'achat (commande la plus récente)
            last_order = record.sale_order_line_ids.mapped('order_id').sorted(key=lambda o: o.date_order, reverse=True)
            record.date_last_purchase = last_order[0].date_order if last_order else None

    @api.depends('quantity_manual_override', 'quantity_mean_ordered')
    def _compute_quantity_planned(self):
        """
        Calcule la quantité prévue pour la prochaine commande.
        """
        for record in self:
            if record.quantity_manual_override:
                record.quantity_planned = record.quantity_manual_override
            else:
                record.quantity_planned = record.quantity_mean_ordered