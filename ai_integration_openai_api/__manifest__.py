{
    'name': 'ChatGPT-Compatible AI Integration',
    'version': '1.0',
    'category': 'Technical',
    'summary': 'Integration for ChatGPT-compatible AI providers',
    'description': """
ChatGPT-Compatible AI Integration
================================
This module provides integration with ChatGPT-compatible AI providers (OpenWebUI, ChatGPT, etc), offering:

* ChatGPT-compatible provider implementation
* Model synchronization
* Advanced parameter configuration
* Usage statistics tracking
* Support for multiple providers using the ChatGPT API format
""",
    'author': 'Bemade',
    'website': 'https://www.bemade.org',
    'depends': [
        'ai_integration',
        'openwebui_integration'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/chatgpt_instance_views.xml',
        'data/chatgpt_provider.xml',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
