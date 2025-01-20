{
    'name': 'MSG Viewer',
    'version': '1.0',
    'category': 'Hidden',
    'summary': 'MSG file viewer for Odoo',
    'description': """
        This module adds support for viewing MSG files directly in Odoo.
        It allows users to preview Outlook MSG files without downloading them.

        It is based on the MSGViewer module by Markiian Karpa
        https://github.com/molotochok/msg-viewer.git
    """,
    'author': 'Bemade inc.',
    'website': 'https://www.bemade.org',
    'depends': [
        'base', 
        'web', 
        'mail'
    ],
    'data': [
        'views/msg_viewer_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'msg_viewer/static/src/js/msg_viewer.js',
            'msg_viewer/static/src/xml/msg_viewer.xml',
            # 'msg_viewer/static/src/css/msg_viewer.css',
        ],
        'msg_viewer.assets': [
            # MSG Viewer library files
            'msg_viewer/static/src/lib/msg-viewer.js',
            'msg_viewer/static/src/lib/scripts/**/*',
            'msg_viewer/static/src/lib/components/**/*',
            'msg_viewer/static/src/lib/styles/**/*',
        ],
        'web.assets_qweb': [
            'msg_viewer/static/src/xml/msg_viewer.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}