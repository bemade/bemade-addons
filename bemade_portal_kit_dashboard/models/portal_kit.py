# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""The dashboard's pages in the kit's page registry: the home (« Dashboard »,
``/my/home`` while the app's switch is on) and the configure sheet under
it. A consumer drawing its own home declares its page and re-declares
``pk_dash_configure`` with that parent."""
from odoo import api, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import pk_static_page

_lt = LazyTranslate(__name__)

PK_DASH_HOME_URL = '/my/home'
PK_DASH_CONFIGURE_URL = '/my/app/dashboard/configure'


class PortalKit(models.AbstractModel):
    _inherit = 'portal.kit'

    @api.model
    def _pk_pages(self):
        return super()._pk_pages() + [
            pk_static_page('pk_dash_page', PK_DASH_HOME_URL, _lt('Dashboard')),
            pk_static_page('pk_dash_configure', PK_DASH_CONFIGURE_URL, _lt('Configure the dashboard'),
                           parent=lambda v: ('pk_dash_page', {})),
        ]
