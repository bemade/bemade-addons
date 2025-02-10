{
    'name': 'Shipping Information on Customer Invoice',
    'version': '18.0.0.1',
    'category': 'Accounting',
    'summary': 'Add shipping carrier information on customer invoices',
    'description': """
        This module adds shipping carrier information to customer invoices:
        * Carrier name
        * Tracking number
        * Billing mode
    """,
    'depends': ['account', 'delivery'],
    'data': [
        'views/report_invoice.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
