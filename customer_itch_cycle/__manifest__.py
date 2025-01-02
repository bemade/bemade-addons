{
    'name': 'Customer Itch Cycle',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Manage customer product cycles and predict future sales',
    'description': """
        This module helps track and manage customer purchasing cycles:
        * Track product purchase cycles per customer
        * Predict next purchase dates
        * Generate opportunities based on predictions
        * Monitor delayed purchases
    """,
    'author': 'DurPro',
    'website': 'https://www.durpro.com',
    'depends': [
        'base',
        'sale',
        'sale_management',
        'crm',
        'sale_crm',
        'base_automation',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/month_data.xml',
        'wizards/apply_to_child_categories.xml',
        'views/itch_cycle_product_partner_view.xml',
        'views/res_partner_view.xml',
        'views/itch_cycle_actions.xml',
        'views/itch_cycle_menu.xml',
        'views/crm_lead_view.xml',
        'views/product_category_view.xml',
        'data/ir_cron_data.xml',
#        'data/crm_automation_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'customer_itch_cycle/static/src/js/cycle_product_partner_list_view.js',
            'customer_itch_cycle/static/src/xml/process_history_button.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
