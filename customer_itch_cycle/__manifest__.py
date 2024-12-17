
{
    'name': 'Customer Itch Cycle Management',
    'version': '1.0',
    'depends': [
        'base',
        'sale_stock'
    ],
    'author': 'Benoit Vézina',
    'category': 'Sales Management',
    'summary': 'Manage customer itch cycles by product for proactive sales engagement.',
    'website': 'https://www.bemade.org',
    'description': "Manage customer itch cycles by product for proactive sales engagement.",
    'license': 'AGPL-3',
    'data': [
        'views/itch_cycle_product_partner_view.xml',
        'views/res_partner_view.xml',
        'views/product_category_view.xml',
        'security/ir.model.access.csv'

    ],
    'installable': True,
    'application': False,
}
