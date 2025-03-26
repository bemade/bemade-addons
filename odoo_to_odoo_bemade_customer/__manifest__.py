{
    'name': 'Odoo to Odoo Bemade Customer',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Connecteur spécifique pour synchronisation avec Odoo.bemade.org',
    'description': """
        Module de synchronisation pour les clients Bemade
        - Connexion sécurisée avec Odoo.bemade.org
        - Synchronisation asynchrone
        - Installation simplifiée
        - Configuration automatique
        - Monitoring et reprise sur erreur
    """,
    'author': 'Bemade',
    'website': 'https://bemade.org',
    'depends': [
        'base', 
        'odoo_to_odoo_sync'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sync_config_views.xml',
        'views/sync_queue_views.xml',
        'views/sync_log_views.xml',
        'views/menus.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
