{
    'name': 'Odoo to Odoo Sync',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Synchronisation bidirectionnelle entre instances Odoo',
    'description': """
        Module de synchronisation bidirectionnelle entre instances Odoo
        - Support multi-instances
        - Synchronisation asynchrone
        - Gestion des conflits
        - Monitoring et reprise sur erreur
    """,
    'author': 'Bemade',
    'website': 'https://bemade.org',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/sync_instance_views.xml',
        'views/sync_model_views.xml',
        'views/sync_queue_views.xml',
        'views/sync_log_views.xml',
        'views/menus.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
