{
    'name': 'Odoo Rsync Backup',
    'version': '18.0.1.0.0',
    'category': 'Administration/Backup',
    'summary': 'Rsync backup for filestore and configuration',
    'sequence': 1,
    'author': 'Bemade',
    'website': 'https://bemade.org',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'auto_database_backup'
    ],
    'data': [
        'views/rsync_config_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
