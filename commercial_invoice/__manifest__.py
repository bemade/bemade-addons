{
    'name': 'Commercial Invoice',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Generate commercial invoices for cross-border shipments',
    'description': """
        Generate commercial invoices for cross-border shipments between Canada and the USA.
        Features:
        - Group multiple invoices into a single commercial invoice
        - Track additional costs (packaging, freight, insurance)
        - Print bilingual commercial invoice reports
    """,
    'author': 'marc@bemade.org',
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'stock_delivery',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/commercial_invoice_sequence.xml',
        'report/commercial_invoice_report.xml',
        'report/report_templates.xml',
        'views/account_move_views.xml',
        'views/commercial_invoice_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
