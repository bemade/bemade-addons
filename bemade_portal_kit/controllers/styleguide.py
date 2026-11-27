# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5357 (P3b2): the kit's style guide, ``/pk/styleguide``.

Every generic component of the shell with the kit's neutral slots, for the
developers building on the kit (internal users only: a portal user gets a
404). ``?theme=dark`` renders the dark theme; the page needs no script.
Task 5199 (P4a): it also answers read fragments (``X-Pk-Fragments``): its
stats carry the key ``page:styleguide:stats``.
Task 5345 (P3c2): it is drawn on the kit's app layout (``pk_app_layout``)
with the neutral brand and synthetic navigation, user and component values.
"""
from werkzeug.exceptions import NotFound

from odoo import _, http
from odoo.http import request

from .pk_app import PortalKitApp

THEMES = ('light', 'dark')


class PkStyleguide(http.Controller):

    @http.route('/pk/styleguide', type='http', auth='user', website=True, sitemap=False)
    def pk_styleguide(self, theme=None, **_kw):
        if not request.env.user.has_group('base.group_user'):
            raise NotFound()
        theme = theme if theme in THEMES else 'light'
        user = request.env.user
        nav = [
            {'key': 'pk_sg_components', 'url': '/pk/styleguide', 'icon': 'list', 'label': _('Components')},
            {'key': 'pk_sg_settings', 'url': '/pk/styleguide#pk_sg_rows', 'icon': 'settings', 'label': _('Rows')},
        ]
        return PortalKitApp._pk_render('bemade_portal_kit.pk_styleguide', {
            'pk_theme': theme,
            'pk_other_theme': 'dark' if theme == 'light' else 'light',
            'pk_rail': nav,
            'pk_tabs': nav,
            'pk_active_nav': 'pk_sg_components',
            'pk_user_initials': ''.join(part[:1] for part in (user.name or '').split()[:2]).upper() or '?',
            'pk_user_name': user.name or '',
            'pk_sg_sorts': [
                {'key': 'name', 'label': _('Name'), 'url': '/pk/styleguide', 'active': True},
                {'key': 'date', 'label': _('Date'), 'url': '/pk/styleguide', 'active': False},
            ],
            'pk_sg_links': [
                {'label': _('A secondary link'), 'url': '/pk/styleguide', 'icon': 'chevron'},
                {'label': _('Plain text'), 'url': False},
            ],
            'pk_sg_history': [
                {'when': '1 Jan 2026 09:00', 'author': _('Sample author'), 'action': _('Edited'), 'tone': 'green',
                 'body': _('A history entry: when, who, what, then the text.'), 'state': ''},
                {'when': '2 Jan 2026 10:30', 'author': _('Sample author'), 'action': '', 'tone': 'ghost',
                 'body': '', 'state': 'cleared'},
            ],
            'pk_sg_flash': {'success': _('A flash banner after a save.'),
                            'error': _('A refusal banner after a post.')},
        })
