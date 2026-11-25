from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        """Task 1737: serve this addon's JS terms (the calendar details'
        « Cancel booking » / « Edit » labels) to frontend pages, like
        bemade_sports_clinic does for the shell."""
        mods = super()._get_translation_frontend_modules_name()
        return mods + ['bemade_sports_clinic_bookings']
