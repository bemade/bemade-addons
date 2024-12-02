{
    'name': 'Extended Module Manager',
    'version': '1.1',
    'summary': 'Gérer les modules via liens symboliques directement depuis ir.modules',
    'category': 'Tools',
    'author': 'Benoît Vézina',
    'depends': ['base'],
    'data': [
#        'views/module_filter_view.xml',
#        'views/module_menu.xml',
        'views/module_view.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}