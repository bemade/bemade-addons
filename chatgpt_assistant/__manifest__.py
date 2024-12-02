
{
    'name': 'ChatGPT Assistant for Discuss',
    'version': '1.0',
    'author': 'Bemade Inc.',
    'category': 'Tools',
    'summary': 'Integrate ChatGPT into Odoo Discuss',
    'depends': ['mail'],
    'data': [
        # 'views/assets.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # '/chatgpt_assistant/static/src/js/discuss_extension.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
