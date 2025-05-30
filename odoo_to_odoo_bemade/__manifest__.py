{
    'name': 'Odoo to Odoo Bemade',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Connecteur universel Bemade pour synchronisation avec instances Odoo',
    'description': """
        Module de synchronisation pour Bemade avec n'importe quelle instance Odoo
        - Support multi-instances
        - Synchronisation asynchrone
        - Gestion des conflits
        - Monitoring et reprise sur erreur
        - Interface administrateur avancée
    """,
    'author': 'Bemade',
    'website': 'https://bemade.org',
    'depends': [
        'base',
        'odoo_to_odoo_sync'
    ],
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
