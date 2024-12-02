{
    'name': 'Odoo Unifi Manager',
    'version': '1.0',
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': [
        'base'
    ],
    'data': [
        'views/firewall_rule_wizard_action.xml',
        'views/firewall_rule_views.xml',
        'views/firewall_rule_template_views.xml',
        # 'views/unify_menu.xml',
        'security/ir.model.access.csv'
    ],
    'installable': True,
    'application': True,
}
