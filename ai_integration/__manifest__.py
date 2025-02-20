{
    'name': 'AI Integration Base',
    'version': '1.0',
    'category': 'Technical',
    'summary': 'Base module for AI integration',
    'description': """
AI Integration Base
===================
This module provides the base framework for integrating various AI providers
into Odoo. It includes:

* Abstract interfaces for AI providers
* Base configuration for AI models
* Common utilities for AI integration
""",
    'author': 'Bemade',
    'website': 'https://www.bemade.org',
    'depends': [
        'base',
        'web',
        'mail',
    ],
    'data': [
        'security/ai_security.xml',
        'security/ir_rule.xml',
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/ai_provider_views.xml',
        'views/ai_provider_instance_views.xml',
        'views/ai_model_views.xml',
        'views/ai_model_stats_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
