{
    'name': 'Ollama Integration',
    'version': '1.0',
    'category': 'Technical',
    'summary': 'Integration with Ollama AI models',
    'description': """
Ollama Integration
==================
This module provides integration with Ollama, allowing you to use local AI models
in your Odoo instance. Features include:

* Connection to local Ollama server
* Support for all Ollama models
* Automatic model discovery and synchronization
* Configurable model parameters
""",
    'author': 'Bemade',
    'website': 'https://www.bemade.org',
    'depends': [
        'ai_integration'
    ],
    'data': [
        'data/ai_provider_data.xml',
        'views/ollama_stats_views.xml',
        'views/ai_provider_instance_views.xml',
        'security/ir.model.access.csv',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
