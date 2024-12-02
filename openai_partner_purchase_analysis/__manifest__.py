{
    'name': 'Partner Purchase Analysis with Optional OpenAI and Queue Job',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Manage OpenAI connection settings',
    'license': 'AGPL-3',
    'description': '''
        This module allows the configuration of OpenAI API connection 
        settings, including API key and Organization ID.
    ''',
    'author': 'Bemade Inc.',
    'depends': [
        'base',
        'sale',
        'product',
        'openai_connector',
        'sale_management',
    ],
    'data': [
        'security/ir.model.access.csv',  # Fichier de sécurité mis à jour
        'data/queue_job_group.xml',
        'views/res_config_settings_view.xml',
        'views/res_partner_view.xml',
        'views/sale_analysis_templates.xml',
        'wizard/partner_purchase_analysis_wizard_view.xml',
    ],
    'external_dependencies': {
        'python': ['openai'],
    },
    'installable': True,
    'application': False,
}