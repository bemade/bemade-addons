# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'OpenWebUI Integration',
    'version': '1.0',
    'summary': 'Integration with OpenWebUI for chatbots',
    'sequence': 10,
    'description': """
OpenWebUI Integration
=====================
This module provides integration with OpenWebUI to create and manage chatbots.

Features:
---------
* Connect to OpenWebUI API
* Manage models and configurations
* Create chatbots with specific behaviors
* Control access to bots by channels and users
""",
    'category': 'Discuss',
    'website': 'https://www.odoo.com/app/discuss',
    'depends': ['mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/openwebui_bot_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
