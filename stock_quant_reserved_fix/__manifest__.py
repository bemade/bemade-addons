{
    'name': 'Stock Quant Reserved Quantity Fix',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Admin tool to manually correct stock quant reserved quantities',
    'description': """
Stock Quant Reserved Quantity Fix
=================================

This module provides a quick fix for situations where stock quants get their 
reserved quantities corrupted when stock operations are cancelled.

Features:
---------
* Server action on stock.quant records for admin users
* Wizard interface to manually set reserved_quantity values
* Easy access through the stock quant list view
* Automatic refresh of current search after update

Usage:
------
1. Navigate to Inventory > Configuration > Locations > Stock Quants
2. Select one or more stock quant records
3. Use the "Fix Reserved Quantity" action from the Action menu
4. Enter the correct reserved quantity value in the wizard
5. Confirm to apply the changes

This module is intended as a temporary fix while investigating the root cause
of the reserved quantity corruption issue in Odoo's core stock operations.
    """,
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/stock_quant_reserved_fix_wizard_views.xml',
        'data/ir_actions_server.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
