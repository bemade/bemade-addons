"""Task 1795 — the client app's appointments (« Rendez-vous », « Réserver »,
the client home's part). Synthetic fixtures only (public repository).

Acceptance criteria covered here:

* UC-B1 A client (portal user without a clinic role) gets « Rendez-vous » at
  ``/my/bookings`` in the client app: their own bookings only — Odoo's
  customer domain (attendee, not organizer, with an appointment type) —
  upcoming first, the past ones folded; a foreign booking (another client's)
  is never shown, not even by id.
* UC-B2 Each upcoming card links Odoo's view page with the event token
  (``/calendar/view/<token>?partner_id=<client>``) and, only while the
  type's minimum notice allows it, the in-app cancel (review round 2:
  ``/my/bookings/<id>/client-cancel``); a past booking has no cancel.
* UC-B3 The client home shows « Prochain rendez-vous » (the next booking, or
  an empty state) and « Mes rendez-vous »; the tab « Rendez-vous ».
* UC-B4 « Réserver »: no published type -> no button; one -> a link to
  ``/appointment/<id>``; two -> a short list of both (name, link).
* UC-B5 Unchanged for the others: a therapist keeps the staff bookings page;
  with the kit switch off a client gets ``appointment_portal_staff``'s page;
  a portal appointment provider without a clinic role keeps that page too.
* UC-B6 The client pages render in French (fr_CA, website-aware).
"""
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from .common import BookingsShellCommon


@tagged('post_install', '-at_install')
class TestClientBookings1795(BookingsShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        cls.client_user = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Robin Client', 'login': 'bk.client@example.com', 'password': 'bk-client-pass',
            'email': 'robin@bk.example.com', 'tz': 'America/Toronto',
            'group_ids': [Command.set([portal])],
        })
        cls.other_user = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Sasha Other', 'login': 'bk.other@example.com', 'password': 'bk-other-pass',
            'email': 'sasha@bk.example.com', 'group_ids': [Command.set([portal])],
        })
        # No published type unless a test publishes one.
        env['appointment.type'].sudo().search([('is_published', '=', True)]).is_published = False
        cls.apt_type.min_cancellation_hours = 24
        now = cls._fixture_now()
        Event = env['calendar.event'].with_context(
            no_mail_to_attendees=True, mail_notrack=True, mail_create_nolog=True)

        def _vals(partner, start, name):
            return {
                'appointment_booker_id': partner.id,
                'appointment_type_id': cls.apt_type.id,
                'name': name,
                'partner_ids': [Command.link(cls.tp.partner_id.id), Command.link(partner.id)],
                'start': start, 'stop': start + timedelta(minutes=45),
                'user_id': cls.tp.id,
            }
        me = cls.client_user.partner_id
        cls.mine_next = Event.create(_vals(me, now + timedelta(days=3), 'Robin upcoming'))
        cls.mine_soon = Event.create(_vals(me, now + timedelta(hours=2), 'Robin soon'))
        cls.mine_past = Event.create(_vals(me, now - timedelta(days=5), 'Robin past'))
        cls.foreign = Event.create(_vals(cls.other_user.partner_id, now + timedelta(days=4),
                                         'Sasha foreign'))
        # Not a booking (no appointment type): never on the page.
        cls.plain_event = Event.create({
            'name': 'Robin plain meeting', 'partner_ids': [Command.link(me.id)],
            'start': now + timedelta(days=2), 'stop': now + timedelta(days=2, hours=1),
        })

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _login_client(self):
        self.authenticate('bk.client@example.com', 'bk-client-pass')

    def _cards(self, tree, section):
        return tree.xpath('//*[@data-pk-section="%s"]//*[@data-sc-client-booking]/@data-sc-client-booking'
                          % section)

    # -- UC-B1 -----------------------------------------------------------
    def test_own_bookings_only(self):
        self._login_client()
        text, tree = self._get('/my/bookings')
        self.assertIsNotNone(self._shell(tree))
        self.assertEqual(self._cards(tree, 'client.upcoming'),
                         [str(self.mine_soon.id), str(self.mine_next.id)])
        self.assertEqual(self._cards(tree, 'client.past'), [str(self.mine_past.id)])
        self.assertTrue(tree.xpath('//details[@data-pk-section="client.past"][not(@open)]'))
        self.assertNotIn(str(self.foreign.access_token), text)
        self.assertNotIn('Sasha', text)
        self.assertFalse(tree.xpath('//*[@data-sc-client-booking="%s"]' % self.foreign.id))
        self.assertFalse(tree.xpath('//*[@data-sc-client-booking="%s"]' % self.plain_event.id))
        # The therapist's name and the type, not the staff page's controls.
        self.assertIn('BK Therapist', text)
        self.assertIn('BK Assessment', text)
        self.assertFalse(tree.xpath('//*[@data-sc-action="booking.edit" or @data-sc-action="booking.cancel"]'))
        # The foreign one cannot be reached by id through the staff routes.
        for url in ('/my/bookings/%s/edit' % self.foreign.id, '/my/bookings/%s/cancel' % self.foreign.id):
            resp = self.url_open(url)
            self.assertIn(resp.status_code, (403, 404), url)
            self.assertNotIn('Sasha', resp.text, url)

    def test_foreign_client_sees_only_theirs(self):
        self.authenticate('bk.other@example.com', 'bk-other-pass')
        text, tree = self._get('/my/bookings')
        self.assertEqual(self._cards(tree, 'client.upcoming'), [str(self.foreign.id)])
        self.assertNotIn('Robin', text)

    def test_empty_state(self):
        self.env['calendar.event'].search([('partner_ids', 'in', self.other_user.partner_id.ids)]).unlink()
        self.authenticate('bk.other@example.com', 'bk-other-pass')
        text, tree = self._get('/my/bookings')
        self.assertFalse(self._cards(tree, 'client.upcoming'))
        self.assertIn('You have no bookings yet.', text)

    # -- UC-B2 -----------------------------------------------------------
    def test_token_links(self):
        self._login_client()
        _text, tree = self._get('/my/bookings')
        pid = self.client_user.partner_id.id

        def card(event):
            return tree.xpath('//*[@data-sc-client-booking="%s"]' % event.id)[0]
        view = card(self.mine_next).xpath('.//a[@data-sc-action="client_booking.view"]/@href')
        self.assertEqual(view, ['/calendar/view/%s?partner_id=%s' % (self.mine_next.access_token, pid)])
        # Review round 2 (deliberate update): the cancel stays in the app
        # (test_client_cancel_1795), no longer Odoo's /calendar/cancel/<token>.
        cancel = tree.xpath('//form[@data-sc-form="client_booking.cancel"]/@action')
        self.assertEqual(cancel, ['/my/bookings/%s/client-cancel' % self.mine_next.id])
        # Inside the minimum notice (24 h): no cancel, the view stays.
        self.assertFalse(card(self.mine_soon).xpath('.//a[@data-sc-action="client_booking.cancel"]'))
        self.assertTrue(card(self.mine_soon).xpath('.//a[@data-sc-action="client_booking.view"]'))
        # Past: no action at all.
        self.assertFalse(card(self.mine_past).xpath('.//a'))

    # -- UC-B3 -----------------------------------------------------------
    def test_client_home_part(self):
        self._login_client()
        _text, tree = self._get('/my/home')
        self.assertEqual(tree.xpath('//*[@data-pk-section="client.next"]//@data-sc-client-booking'),
                         [str(self.mine_soon.id)])
        self.assertTrue(tree.xpath('//a[@data-sc-action="client.bookings"][@href="/my/bookings"]'))
        tabs = tree.xpath("//nav[contains(concat(' ', @class, ' '), ' o_pk_tabs ')]//a/@data-pk-nav-key")
        self.assertEqual(tabs, ['home', 'bookings', 'more'])
        # No booking: the empty state.
        self.authenticate('bk.other@example.com', 'bk-other-pass')
        self.foreign.unlink()
        text, tree = self._get('/my/home')
        self.assertFalse(tree.xpath('//*[@data-pk-section="client.next"]//@data-sc-client-booking'))
        self.assertIn('No upcoming appointments.', text)

    # -- UC-B4 -----------------------------------------------------------
    def _book(self, url='/my/home'):
        _text, tree = self._get(url)
        return tree

    def test_book_none_one_two(self):
        self._login_client()
        for url in ('/my/home', '/my/bookings'):
            tree = self._book(url)
            self.assertFalse(tree.xpath('//*[@data-sc-action="client.book"]'), url)
        self.apt_type.is_published = True
        for url in ('/my/home', '/my/bookings'):
            tree = self._book(url)
            self.assertEqual(tree.xpath('//a[@data-sc-action="client.book"]/@href'),
                             ['/appointment/%s' % self.apt_type.id], url)
        second = self.env['appointment.type'].create({
            'appointment_duration': 1, 'appointment_tz': 'America/Toronto', 'name': 'BK Follow-up',
            'schedule_based_on': 'users', 'staff_user_ids': [Command.set(self.tp.ids)],
            'is_published': True, 'message_intro': '<p>A short <b>follow-up</b> visit.</p>',
        })
        tree = self._book('/my/home')
        self.assertEqual(tree.xpath('//a[@data-sc-action="client.book"]/@data-pk-sheet-open'),
                         ['sc_client_book_sheet'])
        hrefs = tree.xpath('//*[@data-pk-section="client.book_types"]//a/@href')
        self.assertEqual(hrefs, ['/appointment/%s' % t.id for t in (self.apt_type | second).sorted(
            lambda t: (t.sequence, t.id))])
        self.assertIn('A short follow-up visit.', lxml_html.tostring(tree, encoding='unicode'))

    # -- UC-B5 -----------------------------------------------------------
    def test_others_unchanged(self):
        # The therapist: the staff page (organizer side), not the client one.
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        _text, tree = self._get('/my/bookings')
        self.assertTrue(tree.xpath('//*[@data-pk-section="bookings.list"]'))
        self.assertFalse(tree.xpath('//*[@data-pk-section="client.upcoming"]'))
        # Switch off: the client gets appointment_portal_staff's page.
        self._switch(False)
        self._login_client()
        _text, tree = self._get('/my/bookings')
        self.assertIsNone(self._shell(tree))
        self.assertFalse(tree.xpath('//*[@data-pk-section="client.upcoming"]'))

    def test_portal_provider_keeps_stock_page(self):
        provider = self.other_user
        self.apt_type.staff_user_ids = [Command.link(provider.id)]
        self.authenticate('bk.other@example.com', 'bk-other-pass')
        _text, tree = self._get('/my/bookings')
        self.assertFalse(tree.xpath('//*[@data-pk-section="client.upcoming"]'))


@tagged('post_install', '-at_install')
class TestClientBookingsI18n1795(TestClientBookings1795):

    # The inherited tests run once, in their own class.
    test_own_bookings_only = test_foreign_client_sees_only_theirs = test_empty_state = None
    test_token_links = test_client_home_part = test_book_none_one_two = None
    test_others_unchanged = test_portal_provider_keeps_stock_page = None

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

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return ' '.join(resp.text.replace('&#39;', "'").split())

    # -- UC-B6 -----------------------------------------------------------
    def test_client_bookings_in_french(self):
        self.apt_type.is_published = True
        self._login_client()
        text = self._fr('/my/bookings')
        for term in ('Rendez-vous', 'À venir', 'Rendez-vous passés', 'Voir les détails', 'Annuler',
                     'Prendre rendez-vous', 'Annuler ce rendez-vous ?', 'Avec BK Therapist', '45 min'):
            self.assertIn(term, text, term)
        for english in ('Upcoming', 'Past appointments', 'See details', 'Book an appointment'):
            self.assertNotIn(english, text, english)
        text = self._fr('/my/home')
        for term in ('Prochain rendez-vous', 'Mes rendez-vous', 'À venir et passés'):
            self.assertIn(term, text, term)
