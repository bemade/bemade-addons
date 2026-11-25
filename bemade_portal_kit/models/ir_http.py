# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        """Task 5197 (P2): serve the kit's JS terms (``_t``) to frontend
        pages — on a website DB the frontend loads /website/translations,
        which only includes the modules listed here."""
        mods = super()._get_translation_frontend_modules_name()
        return mods + ['bemade_portal_kit']
