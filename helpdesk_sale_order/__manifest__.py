# -*- coding: utf-8 -*-

{
    'name': 'Helpdesk Sale Order',
    'license': 'LGPL-3',
    'version': '18.0.0.1',
    'category' : 'Sales/Sales',
    'summary': """Allows your helpdesk team to create sales orders from helpdesk tickets.""",
    'description': """
       Convert helpdesk tickets into sales orders.

       This feature is useful for companies that sell products or services to their customers 
       and might receive orders through their helpdesk tickets or simply used orders@theirodoo.com 
       as a triage helpdesk ticket.
    """,
    'author': 'Bemade',
    'maintainer': 'it@bemade.org',
    'depends': [
        'sale_management',
        'helpdesk',
        'helpdesk_sale',
        'sale_project'
    ],
    'data': [
        'views/account_move_view.xml',
        'views/helpdesk_ticket_views.xml',
        'views/sale_view.xml',
        'views/helpdesk_team_views.xml'
    ],
    'installable': True,
    'application': False,
}
