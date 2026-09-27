from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        """Task 1542: serve this addon's JS terms (the app shell's OWL
        component and _t strings) to frontend pages — on a website DB the
        frontend loads /website/translations, which only includes the
        modules listed here (core's own pattern, e.g. delivery)."""
        mods = super()._get_translation_frontend_modules_name()
        return mods + ['bemade_sports_clinic']
