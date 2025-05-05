# -*- coding: utf-8 -*-
{
    "name": "Vendor Product E-commerce",
    "version": "18.0.1.0.0",
    "category": "Purchases",
    "author": "Bemade",
    "website": "https://bemade.org",
    "license": "LGPL-3",
    "summary": "Ajoute la gestion des images et des fonctionnalités e-commerce aux produits fournisseurs",
    "description": """
Ce module étend les fonctionnalités du module Vendor Product Management en ajoutant 
la possibilité de gérer des images pour les produits fournisseurs ainsi que des champs
spécifiques pour l'e-commerce.

Fonctionnalités:
- Ajout de champs d'images au modèle vendor.product
- Ajout de champs pour le référencement (SEO)
- Ajout de champs pour la gestion des prix et de la disponibilité sur le site web
- Ajout de champs pour les catégories et les tags
- Intégration avec le site web e-commerce
    """,
    "depends": [
        "base",
        "mail",
        "portal",
        "website_sale",
        "product",
        "purchase",
        "base_import",
        "vendor_product_management",
        "vendor_portal_management",
    ],
    "data": [
        "data/mail_template_vendor_request_approved.xml",
        "data/mail_template_vendor_request_rejected.xml",
        "data/mail_template_vendor_request_ack.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizards/vendor_request_reject_wizard.xml",
        "views/vendor_menu.xml",
        "views/vendor_product_action.xml",
        "views/vendor_product_views.xml",
        "views/vendor_product_portal_templates.xml",
        "views/vendor_product_categories_templates.xml",
        "views/vendor_portal_templates.xml",
        "views/portal_templates.xml",
        "views/portal_menu_templates.xml",
        "views/portal_home_vendor_banner.xml",
        "views/res_users_views.xml",
        "views/res_partner_views.xml",
        "views/vendor_request_views.xml",
        "views/portal_vendor_request_templates.xml",
        "views/portal_vendor_home_template.xml",
        "views/res_config_settings_views.xml",
        "views/vendor_shop_templates.xml",
        "data/vendor_request_sequence.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "st_laurent_portal_vendor/static/src/scss/st_laurent_portal_vendor.scss",
        ],
        "web.assets_frontend": [
            "st_laurent_portal_vendor/static/lib/cropperjs/cropper.min.css",
            "st_laurent_portal_vendor/static/lib/cropperjs/cropper.min.js",
            "st_laurent_portal_vendor/static/src/scss/image_cropper.scss",
            "st_laurent_portal_vendor/static/src/js/image_cropper_simple.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
