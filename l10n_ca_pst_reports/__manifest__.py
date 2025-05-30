{
    'name': 'Canadian PST Numbers on Reports',
    'author': 'Bemade Inc.',
    'version': '1.0',
    'category': 'Accounting/Localizations/Reports',
    'summary': 'Add PST numbers alongside GST/VAT numbers on reports',
    'description': '''
        This module adds Provincial Sales Tax (PST) numbers to reports where GST/VAT numbers
        are already displayed. Supports:
        - Invoice reports
        - Company documents
        - Customer/Vendor forms
    ''',
    'depends': [
        'base',
        'account',
        'l10n_ca',
        'web',  # for external layouts
    ],
    'data': [
        'views/external_layout.xml',
    ],
    'external_dependencies': {
        'python': [],
    },
    'test_external_dependencies': {
        'python': ['pdfminer.six'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
