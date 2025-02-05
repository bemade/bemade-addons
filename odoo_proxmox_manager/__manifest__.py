{
    'name': 'Proxmox Manager',
    'version': '17.0.1.0.0',
    'category': 'Administration',
    'summary': 'Manage Proxmox servers and clusters from Odoo',
    'sequence': 1,
    'author': 'DurPro',
    'website': 'https://www.durpro.com',
    'license': 'LGPL-3',
    'icon': '/odoo_proxmox_manager/static/description/icon.png',
    'depends': [
        'base',
        'web',
        'mail'
    ],
    'data': [
        'security/proxmox_security.xml',
        'security/ir.model.access.csv',
        'views/proxmox_server_views.xml',
        'views/proxmox_cluster_views.xml',
        'views/proxmox_vm_views.xml',
        'views/proxmox_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo_proxmox_manager/static/src/components/**/*',
            'odoo_proxmox_manager/static/src/js/dashboard_view.js',
            'odoo_proxmox_manager/static/src/scss/dashboard.scss',
            'odoo_proxmox_manager/static/src/xml/dashboard.xml',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False
}
