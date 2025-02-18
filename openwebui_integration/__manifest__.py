# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'OpenWebUI Integration',
    'version': '18.0.1.1.0',
    'summary': 'Core integration with OpenWebUI',
    'sequence': 10,
    'description': """
OpenWebUI Integration
=====================
This module provides core integration with OpenWebUI.

Features:
---------
* Connect to OpenWebUI API
* Manage models and configurations
* Base bot functionality and configuration
* Authentication and access control
""",
    'category': 'Discuss',
    'website': 'https://www.odoo.com/app/discuss',
    'depends': ['mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'i18n': True,
    'post_init_hook': 'post_init_hook',
}
