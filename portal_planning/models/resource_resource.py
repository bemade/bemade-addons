# -*- coding: utf-8 -*-

from odoo import fields, models

class ResourceResource(models.Model):
    """Extension du modèle resource.resource pour les fonctionnalités du portail planning."""
    _inherit = 'resource.resource'
    
    portal_modification_auto_approve = fields.Boolean(
        string='Approbation auto des modifications',
        default=False,
        help="Si coché, les modifications de planning via le portail seront automatiquement approuvées pour cette ressource"
    )
    portal_min_hours_before_modification = fields.Integer(
        string='Heures min. avant modification',
        default=24,
        help="Nombre minimum d'heures avant le début du créneau pour permettre une modification via le portail"
    )
    portal_allow_creation = fields.Boolean(
        string='Autoriser création de créneaux',
        default=True,
        help="Si coché, cette ressource peut créer des créneaux de planning via le portail"
    )
    portal_allow_exchange = fields.Boolean(
        string='Autoriser échange de créneaux',
        default=True,
        help="Si coché, cette ressource peut demander des échanges de créneaux via le portail"
    )
