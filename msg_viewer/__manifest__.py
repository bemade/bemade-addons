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
        'mail',
        'documents'
    ],
    'data': [
        'views/msg_viewer_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # MSG viewer components
            'msg_viewer/static/src/models/attachment_card_msg.js',
            'msg_viewer/static/src/components/**/*',
            
            # CSS
            'msg_viewer/static/src/css/**/*',
            
            # MSG Viewer library
            ('include', 'msg_viewer/static/src/lib/msg-viewer-main/dist/**/*'),
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}