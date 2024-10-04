{
    'name': 'Bemade Warn Supplier Overdue',
    'version': '1.0',
    'summary': 'Warn supplier when overdue on purchase order confirmation',
    'description': """
Warn supplier when overdue on purchase order confirmation
===================================
This module adds a mail.message to the purchase order confirmation form when the supplier is overdue.
""",
    'author': 'Benoît Vézina',
    'website': 'https://www.bemade.com',
    'category': 'Purchases',
    'license': 'OPL-1',
    'depends': [
        'purchase',
        'account',
        'mail',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        # 'security/ir.model.access.csv',
    ],
    'demo': [
        # List any demo data files here
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
