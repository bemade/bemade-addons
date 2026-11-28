"""Task 1795, review round 2 (2026-11-27) — a client cancels a booking IN
the app. Synthetic fixtures only (public repository).

Before: « Annuler » followed Odoo's GET ``/calendar/cancel/<token>``, which
lands on the stock ``/appointment/<type>?state=cancel`` page (no message, no
way back into the app).

Acceptance criteria covered here:

* UC-X1 The confirm sheet of an upcoming card posts (CSRF token) to
  ``/my/bookings/<id>/client-cancel`` with the page it came from (« Accueil »
  or « Rendez-vous »); « Voir les détails » stays Odoo's view link.
* UC-X2 Own booking, outside the type's minimum notice: cancelled the way
  Odoo's cancel route does (``action_cancel_meeting``: archived, status
  « cancelled », the « Appointment cancelled by: <client> » chatter line),
  then back to the page it came from with the toast « Appointment
  cancelled » (« Rendez-vous annulé » in French).
* UC-X3 Refusals stay in the app with an error toast and change nothing:
  another client's booking (« cannot be found », nothing of it shown), a
  past booking and one inside the minimum notice (« can no longer be
  cancelled online »), a second cancel of the same booking (« already
  cancelled »). No 500.
* UC-X4 A ``back`` other than the two app pages falls back to
  « Rendez-vous » (no open redirect); a user outside the client app (a
  therapist) gets a 404; a GET is refused.
"""
import re
from urllib.parse import urlsplit

from odoo import Command
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_client_bookings_1795 import TestClientBookings1795


@tagged('post_install', '-at_install')
class TestClientCancel1795(TestClientBookings1795):

    # The inherited tests run once, in their own class.
    test_own_bookings_only = test_foreign_client_sees_only_theirs = test_empty_state = None
    test_token_links = test_client_home_part = test_book_none_one_two = None
    test_others_unchanged = test_portal_provider_keeps_stock_page = None

    def _csrf(self):
        """The session's CSRF token (read once per session, from a page
        that has no toast to pop)."""
        sid = self.opener.cookies.get('session_id')
        cache = self.__dict__.setdefault('_csrf_cache', {})
        if sid not in cache:
            text = self.url_open('/my/app/install').text
            match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', text) \
                or re.search(r'csrf_token:\s*"([^"]+)"', text)
            self.assertTrue(match, 'no CSRF token')
            cache[sid] = match.group(1)
        return cache[sid]

    def _cancel(self, event, back='/my/bookings', allow_redirects=False):
        return self.url_open(
            '/my/bookings/%s/client-cancel' % event.id,
            data={'csrf_token': self._csrf(), 'back': back},
            allow_redirects=allow_redirects)

    def _toast(self, url):
        """The toast host's message and tone on ``url`` (or (None, None))."""
        _text, tree = self._get(url)
        host = tree.xpath('//*[@data-pk-notify]')
        if not host:
            return None, None
        return host[0].get('data-pk-notify'), host[0].get('data-pk-notify-tone')

    def _location(self, resp):
        self.assertIn(resp.status_code, (302, 303), resp.text[:300])
        return urlsplit(resp.headers['Location']).path

    # -- UC-X1 -----------------------------------------------------------
    def test_sheet_posts_in_app(self):
        self._login_client()
        for url in ('/my/bookings', '/my/home'):
            _text, tree = self._get(url)
            forms = tree.xpath('//form[@data-sc-form="client_booking.cancel"]')
            self.assertEqual([f.get('action') for f in forms],
                             ['/my/bookings/%s/client-cancel' % self.mine_next.id] if url == '/my/bookings'
                             else [], url)
            if forms:
                form = forms[0]
                self.assertEqual(form.get('method'), 'post')
                self.assertTrue(form.xpath('.//input[@name="csrf_token"]/@value'))
                self.assertEqual(form.xpath('.//input[@name="back"]/@value'), ['/my/bookings'])
            self.assertFalse(tree.xpath('//a[contains(@href, "/calendar/cancel/")]'), url)
        # The home's card is the next booking (inside the notice: no cancel);
        # with it gone, the home offers the cancel and goes back home.
        self.mine_soon.sudo().unlink()
        _text, tree = self._get('/my/home')
        self.assertEqual(tree.xpath('//form[@data-sc-form="client_booking.cancel"]//input[@name="back"]/@value'),
                         ['/my/home'])
        view = tree.xpath('//a[@data-sc-action="client_booking.view"]/@href')
        self.assertEqual(view, ['/calendar/view/%s?partner_id=%s' % (
            self.mine_next.access_token, self.client_user.partner_id.id)])

    # -- UC-X2 -----------------------------------------------------------
    def test_own_cancel(self):
        second = self.mine_next.copy({'name': 'Robin second', 'partner_ids': self.mine_next.partner_ids.ids})
        self.assertTrue(second.active)
        self._login_client()
        for back, event in (('/my/bookings', self.mine_next), ('/my/home', second)):
            resp = self._cancel(event, back=back)
            self.assertEqual(self._location(resp), back)
            event.invalidate_recordset()
            self.assertFalse(event.active)
            self.assertEqual(event.appointment_status, 'cancelled')
            # Odoo's side effects: the attendees' « canceled » mail and the
            # chatter line naming who cancelled.
            messages = self.env['mail.message'].sudo().search(
                [('model', '=', 'calendar.event'), ('res_id', '=', event.id)])
            bodies = ' '.join(str(body) for body in messages.mapped('body'))
            self.assertIn('Appointment cancelled by: Robin Client', bodies)
            self.assertIn('has been canceled', bodies)
            message, tone = self._toast(back)
            self.assertEqual((message, tone), ('Appointment cancelled', 'success'), back)
            # Shown once.
            self.assertEqual(self._toast(back), (None, None))

    # -- UC-X3 -----------------------------------------------------------
    @mute_logger('odoo.http')
    def test_refusals(self):
        self._login_client()
        cases = (
            (self.foreign, 'This appointment cannot be found.'),
            (self.mine_past, 'This appointment can no longer be cancelled online. Please contact Le Fit Crew.'),
            (self.mine_soon, 'This appointment can no longer be cancelled online. Please contact Le Fit Crew.'),
            (self.plain_event, 'This appointment cannot be found.'),
        )
        for event, expected in cases:
            resp = self._cancel(event)
            self.assertEqual(self._location(resp), '/my/bookings', event.name)
            event.invalidate_recordset()
            self.assertTrue(event.active, event.name)
            self.assertNotEqual(event.appointment_status, 'cancelled', event.name)
            message, tone = self._toast('/my/bookings')
            self.assertEqual((message, tone), (expected, 'error'), event.name)
        # Nothing of the foreign booking shown on the way.
        text, _tree = self._get('/my/bookings')
        self.assertNotIn('Sasha', text)

    def test_double_cancel(self):
        self._login_client()
        self._cancel(self.mine_next)
        self._toast('/my/bookings')
        resp = self._cancel(self.mine_next)
        self.assertEqual(self._location(resp), '/my/bookings')
        self.assertEqual(self._toast('/my/bookings'),
                         ('This appointment is already cancelled.', 'error'))
        self.mine_next.invalidate_recordset()
        self.assertFalse(self.mine_next.active)

    # -- UC-X4 -----------------------------------------------------------
    @mute_logger('odoo.http')
    def test_back_guard_and_others(self):
        self._login_client()
        resp = self._cancel(self.mine_past, back='https://evil.example.com/')
        self.assertEqual(self._location(resp), '/my/bookings')
        # GET: not the route (POST only).
        resp = self.url_open('/my/bookings/%s/client-cancel' % self.mine_next.id, allow_redirects=False)
        self.assertNotIn(resp.status_code, (200, 302, 303))
        self.mine_next.invalidate_recordset()
        self.assertTrue(self.mine_next.active)
        # A therapist (staff app): not this route.
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        resp = self._cancel(self.mine_next)
        self.assertEqual(resp.status_code, 404)
        self.mine_next.invalidate_recordset()
        self.assertTrue(self.mine_next.active)


@tagged('post_install', '-at_install')
class TestClientCancelI18n1795(TestClientCancel1795):

    test_sheet_posts_in_app = test_own_cancel = test_refusals = None
    test_double_cancel = test_back_guard_and_others = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_portal_kit', 'bemade_portal_kit_dashboard', 'bemade_sports_clinic',
             'bemade_sports_clinic_bookings'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.client_user.write({'lang': 'fr_CA'})

    def test_toasts_in_french(self):
        self._login_client()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _text, tree = self._get('/my/bookings')
        self.assertEqual(
            [' '.join(b.text_content().split()) for b in
             tree.xpath('//button[@data-sc-action="client_booking.cancel_confirm"]')],
            ['Annuler le rendez-vous'])
        self._cancel(self.mine_next)
        self.assertEqual(self._toast('/my/bookings'), ('Rendez-vous annulé', 'success'))
        self._cancel(self.mine_next)
        self.assertEqual(self._toast('/my/bookings'), ('Ce rendez-vous est déjà annulé.', 'error'))
        self._cancel(self.mine_soon)
        self.assertEqual(self._toast('/my/bookings')[0],
                         "Ce rendez-vous ne peut plus être annulé en ligne. Veuillez communiquer avec Le Fit Crew.")
        self._cancel(self.foreign)
        self.assertEqual(self._toast('/my/bookings')[0], 'Ce rendez-vous est introuvable.')
