# -*- coding: utf-8 -*-

{
    "name": "Product Supplierinfo Tracking",
    "version": "18.0.3.0.0",
    "license": "AGPL-3",
    "author": "Bemade",
    "category": "Tools",
    "depends": [
        "base",
        "product",
        "stock",
        "sale",
        "purchase",
        "mrp",
    ],
    "description": """
    This module extends basic inventory support for supplierinfo chatter making price 
    updates visible in the chatter.
    """,
    "demo": [],
    'data': [
        'views/product_view.xml',
        'views/supplierinfo.xml',
    ],
    'test': [],
    'installable': True,
    'active': False
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
