{
    'name': 'Interactive AI Voice Assistant',
    'version': '17.0.1.0.0',
    'category': 'Productivity/Communication',
    'summary': 'Natural Language Voice Interaction for Odoo using Open WebUI',
    'sequence': 1,
    'author': 'Benoît Vézina',
    'website': 'https://bemade.org',
    'maintainer': 'it@bemade.org',
    'license': 'LGPL-3',
    'description': """
Interactive AI Voice Assistant for Odoo
=====================================

This module enables natural language voice interaction with Odoo directly in the Discuss interface:
- Voice input processing using Open WebUI models
- Interactive AI chat assistant
- Smart context-aware responses
- Draft mode for new records creation
""",
    'depends': [
        'base',
        'web',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/ai_assistant_views.xml',
        'views/ai_config_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'interactive_discuss_ai/static/src/js/ai_assistant_chat.js',
            'interactive_discuss_ai/static/src/xml/ai_assistant_chat.xml',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'external_dependencies': {
        'python': [
            'requests',
        ],
    },
}
