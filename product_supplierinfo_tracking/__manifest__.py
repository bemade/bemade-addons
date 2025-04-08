# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


{
    "name": "Product Supplierinfo Tracking",
    "version": "18.0.2.0.5",
    "license": "AGPL-3",
    "author": "Bemade",
    "category": "Purchase",
    "depends": [
        "base",
        "product",
        "stock",
        "sale",
        "purchase",
        "mrp",
    ],
    "description": """
    This module extends basic inventory and pricelist management in
    OpenERP to include support for supplierinfo tracking.

    """,
    "demo": [],
    'data': [
        'views/product_view.xml',
        'views/supplierinfo_pricelist.xml',
    ],
    'test': [],
    'installable': True,
    'active': False
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
