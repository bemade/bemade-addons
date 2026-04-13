# -*- coding: utf-8 -*-

{
    "name": "Product Supplier Info Pricing",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Bemade",
    "category": "Inventory/Purchase",
    "depends": [
        "product",
    ],
    "description": """
    This module adds additional pricing fields to supplier information,
    including supplier list price, discount percentage, and calculated price.
    """,
    "demo": [],
    'data': [
        'views/product_supplierinfo_pricing_views.xml',
    ],
    'test': [],
    'installable': True,
    'active': False
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
