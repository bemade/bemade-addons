# -*- coding: utf-8 -*-
{
    "name": "Vendor Orders Management",
    "version": "18.0.1.0.0",
    "category": "Sales",
    "author": "Bemade",
    "website": "https://bemade.org",
    "license": "LGPL-3",
    "summary": "Gestion des commandes pour les vendeurs dans le portail",
    "description": """
Ce module étend les fonctionnalités du portail vendeur en ajoutant la gestion des commandes.

Fonctionnalités:
- Interface pour que les vendeurs puissent voir les commandes de leurs produits
- Système de notification pour les nouvelles commandes
- Gestion des expéditions par les vendeurs
- Suivi des commandes et des statuts d'expédition
    """,
    "depends": [
        "base",
        "mail",
        "portal",
        "website_sale",
        "product",
        "sale",
        "delivery",
        "vendor_product_management",
        "vendor_portal_management",
        "st_laurent_portal_vendor",
    ],
    "data": [
        # "security/security.xml",
        "security/ir.model.access.csv",
        # "views/vendor_order_views.xml",
        # "views/vendor_order_portal_templates.xml",
        # "views/portal_menu_templates.xml",
        # "data/mail_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "st_laurent_vendor_orders/static/src/scss/vendor_orders.scss",
            "st_laurent_vendor_orders/static/src/js/vendor_orders.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
