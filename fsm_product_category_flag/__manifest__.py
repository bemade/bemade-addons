{
    'name': 'FSM Product Category Flag',
    'summary': 'Adds an FSM Product flag on product categories for use in FSM-related logic.',
    'version': '18.0.1.0.0',
    'author': 'Bemade Inc.',
    'license': 'LGPL-3',
    'website': 'https://www.bemade.org',
    'category': 'Product',
    'depends': ['product'],
    'description': '''
FSM Product Category Flag
=========================

This addon adds a simple **FSM Product** boolean on product categories.

It is intended to be used by FSM-related reporting or business logic, such as
the FSM Job Profitability module, to distinguish which product categories
should be considered FSM service products when computing revenue or other
metrics.
''',
    'data': [
        'views/product_category_views.xml',
    ],
    'installable': True,
    'application': False,
}
