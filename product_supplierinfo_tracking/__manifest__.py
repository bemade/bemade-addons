# -*- coding: utf-8 -*-

{
    "name": "Product Supplierinfo Tracking",
    "version": "19.0.3.1.0",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "category": "Tools",
    "depends": [
        "base",
        "product",
        "stock",
        "sale",
        "purchase",
        "mrp",
    ],
    "external_dependencies": {"python": ["markupsafe"]},
    "description": """
Product Supplierinfo Tracking
=============================

Tracks vendor price lines (``product.supplierinfo``) in the chatter and posts
every change on the product page (template and variant).

Each changed field gets its own readable line: the field's label in the
user's language and a formatted value. Prices show as money in the line's
currency with at least two decimals, keeping the real decimals a vendor price
carries (5.945 stays 5.945); vendors and other links show their name;
quantities and dates use the user's language format. User-typed text is
escaped.
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
