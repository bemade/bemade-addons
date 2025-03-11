# -*- coding: utf-8 -*-
{
    'name': 'Unifi Integration',
    'version': '1.0',
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
    'author': 'Your Company',
    'website': 'https://www.bemade.org',
    'depends': ['base', 'web', 'website'],
    'data': [
        'security/udm_pro_security.xml',
        'security/ir.model.access.csv',
        'views/udm_configuration_views.xml',
        'views/udm_system_info_views.xml',
        'views/udm_network_views.xml',
        'views/udm_vlan_views.xml',
        'views/udm_device_views.xml',
        'views/udm_user_views.xml',
        'views/udm_settings_views.xml',
        'views/udm_firewall_views.xml',
        'views/udm_network_config_views.xml',
        'views/udm_menu_views.xml',
        'views/templates.xml',
        'views/udm_pro_docs_templates.xml',
        'wizards/udm_site_import_wizard_views.xml',
        'wizards/views/udm_mfa_wizard_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['requests'],
    },
    'assets': {
        'web.assets_backend': [
            'unifi_integration/static/src/css/udm_pro.css',
        ],
    },
}
