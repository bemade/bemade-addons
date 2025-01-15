{
    'name': 'Purchase Customer Requisition',
    'version': '1.0',
    'category': 'Purchase',
    'summary': 'Link customer requisition references to purchase orders',
    'description': """
        This module allows to:
        * Store customer-specific requisition references for suppliers
        * Automatically add these references to purchase order lines
        * Track customer requisition numbers across purchase orders
    """,
    'license': 'LGPL-3',
    'depends': [
        'purchase', 
        'sale_purchase',
        'purchase_requisition'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/customer_supplier_requisition_views.xml',
        'views/purchase_views.xml',
        'views/purchase_requisition_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}