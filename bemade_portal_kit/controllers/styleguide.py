# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5357 (P3b2): the kit's style guide, ``/pk/styleguide``.

Every generic component of the shell with the kit's neutral slots, for the
developers building on the kit (internal users only: a portal user gets a
404). ``?theme=dark`` renders the dark theme; the page needs no script.
Task 5199 (P4a): it also answers read fragments (``X-Pk-Fragments``): its
stats carry the key ``page:styleguide:stats``.
"""
from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request

from .pk_app import PortalKitApp

THEMES = ('light', 'dark')


class PkStyleguide(http.Controller):

    @http.route('/pk/styleguide', type='http', auth='user', website=True, sitemap=False)
    def pk_styleguide(self, theme=None, **_kw):
        if not request.env.user.has_group('base.group_user'):
            raise NotFound()
        theme = theme if theme in THEMES else 'light'
        return PortalKitApp._pk_render('bemade_portal_kit.pk_styleguide', {
            'pk_theme': theme,
            'pk_other_theme': 'dark' if theme == 'light' else 'light',
        })
