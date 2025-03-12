# -*- coding: utf-8 -*-
{
    "name": "Batch Picking - Create One Bill",
    "version": "18.0.1.0.0",
    "category": "Inventory/Purchase",
    "summary": "Créer une seule facture fournisseur pour tous les bons de commande d'un batch picking",
    "description": """
        Ce module permet de générer une seule facture fournisseur pour tous les bons de commande
        associés à un batch picking.
        
        Fonctionnalités:
        - Option pour initialiser les quantités à zéro lors de la création d'un batch
        - Bouton pour créer une facture groupée à partir d'un batch de transferts
        - Validation que tous les bons de commande proviennent du même fournisseur
        - Suivi des factures créées directement depuis le batch
    """,
    "author": "Pneumac",
    "website": "https://www.pneumac.ca",
    "depends": [
        "stock_picking_batch",
        "purchase",
        "purchase_stock",
        "account",
        "account_reports",
    ],
    "data": [
        "wizard/stock_picking_to_batch_views.xml",
        "views/stock_picking_batch_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
