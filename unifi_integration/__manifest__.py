{
    'name': 'Unifi Integration',
    'version': '1.0.1',
    'category': 'Network/Documentation',
    'summary': 'Store and manage Unifi configurations',
    'description': """
Unifi Integration
=================
This module allows you to:
* Connect to Unifi devices and retrieve configurations
* Store configuration history in the database
* Generate documentation of network setup
* Compare configurations over time
""",
    'author': 'Bemade',
    'website': 'https://www.bemade.org',
    'depends': [
        'base', 
        'web',
        'mail'
    ],
    'data': [
        # Sécurité et règles d'accès
        'security/unifi_security.xml',
        'security/ir.model.access.csv',
        # Vues et actions pour les modèles unifi_ (doivent être chargées avant les menus qui y font référence)
        'views/unifi_actions.xml',
        'views/unifi_site_views.xml',
        # Menus (doivent être chargés après les actions auxquelles ils font référence)
        'views/unifi_menu_views.xml',
        # Wizards (doivent être chargés après les menus auxquels ils font référence)
        'wizards/unifi_site_import_wizard_views.xml',
        # Temporairement commenté pour permettre l'installation du module
        # 'views/unifi_auth_session_views.xml',
        # 'views/unifi_mfa_views.xml',
        # 'views/unifi_api_log_views.xml',
        # 'views/unifi_sync_job_views.xml',
        'views/unifi_device_views.xml',
        'views/unifi_network_views.xml',
        'views/unifi_vlan_views.xml',
        'views/unifi_user_views.xml',
        'views/unifi_firewall_views.xml',
        'views/unifi_port_forward_views.xml',
        'views/unifi_system_info_views.xml',
        'views/unifi_dns_views.xml',
        'views/unifi_dns_config_views.xml',
        'views/unifi_routing_views.xml',
        'views/unifi_routing_config_views.xml',
        'views/unifi_wifi_views.xml',
        'views/unifi_vpn_views.xml',
        'views/unifi_api_config_views.xml',
        'views/unifi_dashboard_views.xml',
        # Templates
        'views/templates.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
            'unifi_integration/static/src/components/import_site_button/import_site_button.js',
            'unifi_integration/static/src/components/import_site_button/import_site_button.xml',
            'unifi_integration/static/src/css/unifi.css',
        ],
    },
    'external_dependencies': {
        'python': [
            'requests',
        ],
    },
}
