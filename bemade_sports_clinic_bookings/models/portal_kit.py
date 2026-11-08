"""Task 5196 — the bookings pages and nav entry, registered on the kit's
``portal.kit`` hooks (per database: they exist only where this addon is
installed; before, ``controllers/bookings.py`` added them to the clinic's
module-level ``PAGES`` at import time, in every database of the worker).

Task 1737: the edit / cancel pages are sub-pages of « Mes rendez-vous » in
the shell's parent registry (back chevron + crumbs); the list / calendar
are registered so a ``return_url`` to them is honoured. Like « Events » /
« Timesheets » (rail + « Plus », ``RAIL_PLUS``), the list is a « Plus »
page: its parent is sc_app_more (the shell rule: a non-top-level page
declares a parent — bemade_sports_clinic test_app_shell_nav_1579).
"""
from odoo import api, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import Page, pk_nav
from odoo.addons.bemade_sports_clinic.models.sc_app_roles import EVERYONE, RAIL_PLUS

_lt = LazyTranslate(__name__)

BOOKINGS_PAGE = 'sc_app_bookings'
# Labels first, keys zipped in (babel's extractor would take a literal that
# follows an _lt() call in the same tuple for a term).
_PAGE_LABELS = (_lt('Edit booking'), _lt('Cancel booking'))
_PAGE_KEYS = (('sc_app_booking_edit', 'edit'), ('sc_app_booking_cancel', 'cancel'))


def _booking_card_enabled(ctx):
    """The appointment addon flags its portal home card
    (``booking_card_enable``, passed in by the shell's nav context)."""
    return bool(ctx.get('booking_card_enable'))


class SportsClinicBookingsPortalKit(models.AbstractModel):
    _inherit = 'portal.kit'

    @api.model
    def _pk_nav(self):
        return list(super()._pk_nav()) + [
            pk_nav('bookings', _lt('Bookings'), 'bookings', '/my/bookings', EVERYONE, 80,
                   RAIL_PLUS, requires=_booking_card_enabled,
                   subtitle=_lt('Your appointments')),
        ]

    @api.model
    def _pk_pages(self):
        pages = [Page(
            BOOKINGS_PAGE, url='/my/bookings', label=self.pk_nav_label('bookings'),
            path=r'/my/bookings(?:/calendar)?', parent=lambda v: ('sc_app_more', {}))]
        for (key, suffix), label in zip(_PAGE_KEYS, _PAGE_LABELS):
            pages.append(Page(
                key, parent=lambda v: (BOOKINGS_PAGE, {}), label=label,
                url=lambda v, _s=suffix: '/my/bookings/%s/%s' % (v['booking'].id, _s)))
        return list(super()._pk_pages()) + pages
