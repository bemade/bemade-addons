"""Task 1596 — the bookings list sort control on the app shell.

Acceptance criteria:

* UC-S1 The shell bookings list shows a date sort control (oldest first /
  newest first, the labels of appointment_portal_staff's
  ``searchbar_sortings``); the active choice is marked ``aria-checked``
  (task 1607: the list header's sort menu, ``role="menuitemradio"``).
  With no explicit choice the segment's default is active (upcoming:
  oldest first; past / all: newest first).
* UC-S2 ``sortby`` is honoured both ways: ``date`` lists bookings oldest
  first, ``date_desc`` newest first.
* UC-S3 An explicit sort choice survives switching segments: the upcoming /
  past / all segment links (and the sort links) carry ``sortby`` together
  with the active filters (appointment type, date range); the filter form
  re-submits it. Without an explicit choice the segment links carry no
  ``sortby`` (each segment keeps its own default). The calendar segment
  link is unchanged.
* UC-S4 (task 1607) The sort sits in the shell's list header, condensed to
  the right, directly above the bookings list; the list has no « + Ajouter ».
"""
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from odoo import Command
from odoo.tests import tagged

from .common import BookingsShellCommon


@tagged('post_install', '-at_install')
class TestBookingsSort(BookingsShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start = cls.booking_soon.start + timedelta(days=2)
        cls.booking_later = cls.env['calendar.event'].with_context(
            no_mail_to_attendees=True, mail_notrack=True, mail_create_nolog=True,
        ).create({
            'appointment_booker_id': cls.client.id,
            'appointment_type_id': cls.apt_type.id,
            'name': 'BK Assessment - Quinn Client',
            'partner_ids': [Command.link(cls.tp.partner_id.id), Command.link(cls.client.id)],
            'start': start, 'stop': start + timedelta(hours=1),
            'user_id': cls.tp.id,
        })

    def setUp(self):
        super().setUp()
        self._switch(True)
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')

    @staticmethod
    def _ids(tree):
        return [int(x) for x in tree.xpath('//*[@data-sc-booking-id]/@data-sc-booking-id')]

    @staticmethod
    def _sort_links(tree):
        return {a.get('data-sc-sort'): a for a in tree.xpath('//*[@data-sc-section="bookings.sort"]//a[@data-sc-sort]')}

    @staticmethod
    def _active_sort(tree):
        return tree.xpath('//*[@data-sc-section="bookings.sort"]//a[@aria-checked="true"]/@data-sc-sort')

    @staticmethod
    def _segment_hrefs(tree):
        return {a.get('data-sc-tab'): a.get('href') for a in tree.xpath('//nav[@data-sc-tabs]//a')}

    @staticmethod
    def _query(href):
        parts = urlsplit(href)
        return parts.path, {k: v[0] for k, v in parse_qs(parts.query).items()}

    def test_sort_control_defaults(self):
        """UC-S1"""
        _text, tree = self._get('/my/bookings')
        links = self._sort_links(tree)
        self.assertEqual(sorted(links), ['date', 'date_desc'])
        self.assertIn('oldest first', links['date'].text_content())
        self.assertIn('newest first', links['date_desc'].text_content())
        self.assertEqual(self._active_sort(tree), ['date'])
        _text, tree = self._get('/my/bookings?filterby=past')
        self.assertEqual(self._active_sort(tree), ['date_desc'])
        _text, tree = self._get('/my/bookings?filterby=all')
        self.assertEqual(self._active_sort(tree), ['date_desc'])

    def test_sortby_both_ways(self):
        """UC-S2"""
        _text, tree = self._get('/my/bookings?sortby=date')
        self.assertEqual(self._ids(tree), [self.booking_soon.id, self.booking_later.id])
        _text, tree = self._get('/my/bookings?sortby=date_desc')
        self.assertEqual(self._ids(tree), [self.booking_later.id, self.booking_soon.id])
        self.assertEqual(self._active_sort(tree), ['date_desc'])
        _text, tree = self._get('/my/bookings?filterby=all&sortby=date')
        self.assertEqual(self._ids(tree), [self.booking_past.id, self.booking_soon.id, self.booking_later.id])
        _text, tree = self._get('/my/bookings?filterby=all&sortby=date_desc')
        self.assertEqual(self._ids(tree), [self.booking_later.id, self.booking_soon.id, self.booking_past.id])

    def test_sort_links_keep_segment_and_filters(self):
        """UC-S3 (sort links)"""
        type_id = str(self.apt_type.id)
        _text, tree = self._get('/my/bookings?filterby=past&appointment_type_id=%s' % type_id)
        path, query = self._query(self._sort_links(tree)['date'].get('href'))
        self.assertEqual(path, '/my/bookings')
        self.assertEqual(query, {'filterby': 'past', 'appointment_type_id': type_id, 'sortby': 'date'})
        # Following it sorts the past segment oldest first.
        _text, tree = self._get(self._sort_links(tree)['date'].get('href'))
        self.assertEqual(self._active_sort(tree), ['date'])

    def test_sortby_preserved_across_segments(self):
        """UC-S3 (segments)"""
        type_id = str(self.apt_type.id)
        _text, tree = self._get(
            '/my/bookings?filterby=upcoming&sortby=date_desc&appointment_type_id=%s'
            '&date_from=2000-01-01&date_to=2099-12-31' % type_id)
        hrefs = self._segment_hrefs(tree)
        for key in ('upcoming', 'past', 'all'):
            path, query = self._query(hrefs[key])
            self.assertEqual(path, '/my/bookings', key)
            self.assertEqual(query, {
                'filterby': key, 'sortby': 'date_desc', 'appointment_type_id': type_id,
                'date_from': '2000-01-01', 'date_to': '2099-12-31',
            }, key)
        self.assertEqual(hrefs['calendar'], '/my/bookings/calendar')
        self.assertEqual(tree.xpath('//form[@data-sc-section="bookings.filters"]//input[@name="sortby"]/@value'),
                         ['date_desc'])
        # The choice survives the switch: upcoming newest first -> all, still newest first.
        _text, tree = self._get(hrefs['all'])
        self.assertEqual(self._active_sort(tree), ['date_desc'])
        self.assertEqual(self._ids(tree), [self.booking_later.id, self.booking_soon.id, self.booking_past.id])
        # And the other way: past oldest first -> upcoming keeps oldest first.
        _text, tree = self._get('/my/bookings?filterby=past&sortby=date')
        _text, tree = self._get(self._segment_hrefs(tree)['upcoming'])
        self.assertEqual(self._active_sort(tree), ['date'])

    def test_no_explicit_sort_segment_defaults(self):
        """UC-S3 (no explicit choice: each segment keeps its default)"""
        _text, tree = self._get('/my/bookings')
        hrefs = self._segment_hrefs(tree)
        for key in ('upcoming', 'past', 'all'):
            path, query = self._query(hrefs[key])
            self.assertEqual((path, query), ('/my/bookings', {'filterby': key}), key)
        self.assertFalse(tree.xpath('//form[@data-sc-section="bookings.filters"]//input[@name="sortby"]'))
        _text, tree = self._get(hrefs['past'])
        self.assertEqual(self._active_sort(tree), ['date_desc'])

    def test_sort_in_the_list_header(self):
        """UC-S4"""
        _text, tree = self._get('/my/bookings')
        headers = tree.xpath('//div[contains(@class, "o_sc_list_header")][@data-sc-section="bookings.header"]')
        self.assertEqual(len(headers), 1)
        header = headers[0]
        self.assertTrue(header.xpath('.//*[@data-sc-section="bookings.sort"]//a[@role="menuitemradio"]'))
        self.assertFalse(header.xpath('.//*[contains(@class, "o_sc_list_add")]'))
        following = header.getnext()
        self.assertIsNotNone(following)
        self.assertEqual(following.get('data-sc-section'), 'bookings.list')
