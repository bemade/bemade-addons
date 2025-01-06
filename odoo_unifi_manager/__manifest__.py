{
    'name': 'Odoo Unifi Manager',
    'version': '1.0',
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'base_setup'
    ],
    'external_dependencies': {
        'python': ['pyunifi'],
    },
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/unifi_action.xml',
        'views/unifi_controller_views.xml',
        'views/unifi_client_views.xml',
        'views/unifi_site_views.xml',        
        'views/unifi_device_views.xml',
        'views/unifi_network_views.xml',
        'views/unifi_wifi_views.xml',
        'views/unifi_firewall_group_views.xml',
        'views/unifi_port_forward_views.xml',
        'views/unifi_firewall_rule_template_views.xml',
        'views/unifi_firewall_rule_views.xml',
        'views/unifi_dashboard.xml',
        'views/unifi_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # External Libraries
            'odoo_unifi_manager/static/lib/chart.js/Chart.bundle.min.js',
            
            # Styles
            'odoo_unifi_manager/static/src/scss/dashboard.scss',
            
            # Dashboard Components
            ('include', 'web._assets_helpers'),
            ('include', 'web._assets_backend_helpers'),
            'odoo_unifi_manager/static/src/js/dashboard_view.js',
            'odoo_unifi_manager/static/src/xml/dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
}
