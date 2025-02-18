# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'OpenWebUI Integration Chat',
    'version': '1.0',
    'summary': 'Chat integration with OpenWebUI for Discuss',
    'sequence': 11,
    'description': """
OpenWebUI Integration Chat
=========================
This module extends OpenWebUI Integration to provide chatbot features in Discuss.

Features:
---------
* Integrate chatbots with Discuss channels
* Control access to bots by channels and users
* Chat-specific bot configurations and behaviors
""",
    'category': 'Discuss',
    'website': 'https://www.odoo.com/app/discuss',
    'depends': [
        'mail', 
        'openwebui_integration'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/discuss_channel_views.xml',
        'views/openwebui_bot_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
