{
    'name': 'Commercial Invoice',
    'version': '19.0.1.3.0',
    'category': 'Accounting',
    'summary': 'Generate commercial invoices for cross-border shipments',
    'description': """
        Generate commercial invoices for cross-border shipments between Canada and the USA.
        Features:
        - Group multiple invoices into a single commercial invoice
        - Build a commercial invoice from selected customer deliveries
          (explicit picking selection or partner-search fallback)
        - Track additional costs (packaging, freight, insurance)
        - Print bilingual commercial invoice reports
    """,
    'author': 'marc@bemade.org',
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'stock_delivery',
        'delivery',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/commercial_invoice_sequence.xml',
        'data/stock_picking_actions.xml',
        'report/commercial_invoice_report.xml',
        'report/report_templates.xml',
        'views/account_move_views.xml',
        'views/commercial_invoice_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
