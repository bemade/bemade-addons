# -*- coding: utf-8 -*-
{
    'name': 'OpenWebUI Integration Product',
    'version': '18.0.1.0.1',
    'summary': "AI-powered actions integration for Odoo products",
    'description': """
OpenWebUI Integration Product Module
====================================

This module extends OpenWebUI Integration to add AI-powered features to product management.
""",
    'author': 'Benoît Vézina',
    'license': 'LGPL-3',
    'website': 'https://www.bemade.org',
    'depends': ['product', 'openwebui_integration'],
    'data': [
         'security/ir.model.access.csv',
         'views/product_template_view.xml',
         'views/product_template_action.xml',
         'wizard/category_suggestion_wizard_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
