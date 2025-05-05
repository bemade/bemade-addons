# -*- coding: utf-8 -*-
# Portal Partner Manager Module Manifest
{
    "name": "Portal Partner Manager",
    "version": "18.0.1.0.0",
    "category": "Website/Website",
    "summary": "Allows portal users to edit their parent company and add contacts",
    "description": """
        This module allows portal users to modify their parent company and add contacts from the portal. It includes advanced access management, company edit restrictions, and contact management directly from the portal interface.
    """,
    "author": "Odoo SA",
    "website": "https://www.odoo.com",
    "depends": [
        "base",
        "portal",
        "contacts",
        "mail",
        "web_editor",
        "website",
        "website_mail",
        "portal_rating",
        "http_routing"
    ],
    "data": [
        "security/portal_security.xml",
        "security/ir.model.access.csv",
        "security/portal_partner_manager_rules.xml",
        "views/res_partner_views.xml",
        "views/portal_company_templates.xml",
        "views/portal_contact_templates.xml",
        #"views/portal_sibling_templates.xml",
        "views/portal_menu_templates.xml",
        "views/portal_set_password.xml",
        "views/portal_archive_contact_confirm.xml",
        "views/portal_activity_log_views.xml"
    ],
    "assets": {
        "web.assets_frontend": [
            
        ]
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
