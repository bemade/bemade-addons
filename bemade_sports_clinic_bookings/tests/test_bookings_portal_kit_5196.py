"""Task 5196 — the bookings nav entry and pages, on this addon's own
``portal.kit`` hooks (they were added to the clinic's module-level
``PAGES`` at import time). Synthetic fixtures only.

Acceptance criteria:

* UC-BK1 The « bookings » entry is a rail + « Plus » entry for every app
  role, gated by ``requires``: only when the shell's nav context says the
  appointment card is enabled (``booking_card_enable``); never a phone tab.
* UC-BK2 The list / calendar page is registered (a ``return_url`` to it is
  honoured, under « Plus »); the edit / cancel pages are its sub-pages.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBookingsPortalKit5196(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tp = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'bk5196.tp', 'login': 'bk5196.tp@example.com',
            'group_ids': [Command.set([
                cls.env.ref('base.group_portal').id,
                cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id])],
        })

    def _keys(self, roles, placement, ctx):
        return [e['key'] for e in self.env['portal.kit'].pk_visible_nav(roles, placement, ctx)]

    # -- UC-BK1 -----------------------------------------------------------
    def test_requires_gates_bookings(self):
        roles = self.tp._sc_app_roles()
        self.assertNotIn('bookings', self._keys(roles, 'rail', {'booking_card_enable': False}))
        self.assertNotIn('bookings', self._keys(roles, 'rail', {}))
        self.assertIn('bookings', self._keys(roles, 'rail', {'booking_card_enable': True}))
        self.assertIn('bookings', self._keys(roles, 'plus', {'booking_card_enable': True}))
        # Never a phone tab: bookings live under « Plus » on the phone.
        self.assertNotIn('bookings', self._keys(roles, 'tab', {'booking_card_enable': True}))
        # Between « Timesheets » and « More » on the rail, as before.
        rail = self._keys(roles, 'rail', {'booking_card_enable': True})
        self.assertEqual(rail[rail.index('bookings') - 1:rail.index('bookings') + 2],
                         ['timesheets', 'bookings', 'more'])

    # -- UC-BK2 -----------------------------------------------------------
    def test_pages(self):
        kit = self.env['portal.kit']
        self.assertEqual(kit.pk_match_url('/my/bookings?filterby=past')[0], 'sc_app_bookings')
        self.assertEqual(kit.pk_match_url('/my/bookings/calendar')[0], 'sc_app_bookings')
        booking = self.env['calendar.event'].create({'name': 'Kit 5196 booking'})
        nav = kit.pk_resolve('sc_app_booking_edit', {'booking': booking})
        self.assertEqual(nav['parent_url'], '/my/bookings')
        self.assertEqual([url for _label, url in nav['crumbs']], ['/my/app/more', '/my/bookings'])
        self.assertEqual(str(kit.pk_pages()['sc_app_booking_cancel'].url({'booking': booking})),
                         '/my/bookings/%s/cancel' % booking.id)
