{
    'name': 'OpenAI Connector',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Manage OpenAI connection settings',
    'license': 'AGPL-3',
    'description': '''
        This module allows the configuration of OpenAI API connection 
        settings, including API key and Organization ID.
    ''',
    'author': 'Bemade Inc.',
    'depends': ['base_setup'],
    'data': [
        'views/res_config_settings_views.xml',
        'security/ir.model.access.csv',
    ],
    'external_dependencies': {
        'python': ['openai'],
    },
    'installable': True,
    'application': False,
}