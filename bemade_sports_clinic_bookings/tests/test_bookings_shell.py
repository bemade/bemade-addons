"""Task 1540 — the bookings pages on the app shell (glue addon).

Acceptance criteria:

* UC-B1 Switch OFF: /my/bookings and /my/bookings/calendar render the
  appointment_portal_staff templates unchanged (no shell marker).
* UC-B2 Switch ON (therapist who is appointment staff): the list renders on
  the shell with the same search (upcoming by default, past / all segments),
  one row per booking; the calendar is the shared sc_calendar component on
  the unchanged feed; « Réservations » is in the navigation.
* UC-B3 The feed keeps its shape; no inline script / style in this addon's
  shell views.
* UC-B4 fr_CA: the shell bookings page renders in French.
"""
import re

from odoo.tests import tagged

from .common import BookingsShellCommon


@tagged('post_install', '-at_install')
class TestBookingsShell(BookingsShellCommon):

    def test_switch_off_legacy(self):
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        for url in ('/my/bookings', '/my/bookings/calendar'):
            text, tree = self._get(url)
            self.assertIsNone(self._shell(tree), url)
            self.assertNotIn('data-sc-app-shell', text)

    def test_list_in_shell(self):
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        _text, tree = self._get('/my/bookings')
        self.assertIsNotNone(self._shell(tree))
        self.assertEqual(tree.xpath('//nav[@data-sc-tabs]//a/@data-sc-tab'),
                         ['upcoming', 'past', 'all', 'calendar'])
        ids = [int(x) for x in tree.xpath('//*[@data-sc-booking-id]/@data-sc-booking-id')]
        self.assertEqual(ids, [self.booking_soon.id])
        self.assertIn('bookings', tree.xpath('//nav[contains(@class, "o_sc_rail_nav")]//a/@data-sc-nav-key'))
        _text, tree = self._get('/my/bookings?filterby=past')
        ids = [int(x) for x in tree.xpath('//*[@data-sc-booking-id]/@data-sc-booking-id')]
        self.assertEqual(ids, [self.booking_past.id])

    def test_calendar_in_shell(self):
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        text, tree = self._get('/my/bookings/calendar')
        self.assertIsNotNone(self._shell(tree))
        props = self._calendar_props(tree)
        self.assertEqual(props['feedUrl'], '/my/bookings/calendar/data')
        self.assertIn('client', [key for key, _label in props['detailKeys']])
        self.assertNotIn('/web/static/lib/fullcalendar', text)
        start = self.booking_soon.start.strftime('%Y-%m-%dT00:00:00Z')
        feed = self.url_open('/my/bookings/calendar/data?start=%s&end=2099-01-01T00:00:00Z' % start).json()
        self.assertIn(self.booking_soon.id, [row['id'] for row in feed])

    def test_lint_no_inline_script_or_style(self):
        views = self.env['ir.ui.view'].search([('key', '=like', 'bemade_sports_clinic_bookings.%')])
        self.assertTrue(views)
        for view in views:
            arch = view.arch_db or ''
            self.assertNotIn('<script', arch.lower(), view.key)
            self.assertFalse(re.search(r'\sstyle\s*=', arch), view.key)

    def test_french(self):
        """fr_CA, website-aware (fr_CA on every website + the frontend_lang
        cookie when ``website`` is installed)."""
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic', 'bemade_sports_clinic_bookings'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [(4, fr_lang.id)]
        self.tp.write({'lang': 'fr_CA'})
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        text, _tree = self._get('/my/bookings')
        for term in ('À venir', 'Passées', 'Calendrier', 'Tous les types', 'Filtres', 'Réservations'):
            self.assertIn(term, text, term)
