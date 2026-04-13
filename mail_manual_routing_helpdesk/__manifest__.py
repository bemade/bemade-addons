# -*- coding: utf-8 -*-
{
    'name': 'Lost Messages Routing - Helpdesk Integration',
    'version': '18.0.1.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'Create helpdesk tickets from lost messages',
    'description': """
Lost Messages Routing - Helpdesk Integration
=============================================

Bridge module that adds helpdesk ticket creation capability to the 
lost messages triage workflow.

This module auto-installs when both mail_manual_routing_ux and helpdesk 
are installed.

Features:
- Create helpdesk tickets from lost messages
- Select target helpdesk team
- Automatic categorization after ticket creation
    """,
    'author': 'Durpro',
    'website': 'https://www.durpro.com',
    'license': 'LGPL-3',
    'depends': [
        'mail_manual_routing_ux',
        'helpdesk',
    ],
    'data': [
        'views/mail_finance_triage_wizard_views.xml',
    ],
    'auto_install': True,
    'installable': True,
    'application': False,
}
