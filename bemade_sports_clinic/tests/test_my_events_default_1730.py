"""Task 1730 — the events list and calendar open on « My events » for a
treatment professional. Synthetic fixtures only.

Context: a therapist looking for her events (to fill her timesheets) landed
on everyone's events; « My events » existed but was one tap away. The view
the page opens on changes, nothing else (the read rules are unchanged).

Acceptance criteria covered here:

* UC-1 A treatment professional (portal or internal) opening /my/events with
  no view in the URL (no ``view_type``, no ``assigned_user_id``) sees only
  the events assigned to her, the « My events » chip active.
* UC-2 An explicit view sticks: ``view_type=all`` (the « All » chip, whose
  link names it) shows every event; the pager, the segment links and the
  filter form keep the chosen view.
* UC-3 Coaches and administrators are unchanged: no view in the URL = « All ».
* UC-4 The calendar does the same: a professional lands on « My events »
  (the feed is handed the view, the filter panel stays closed), « All »
  sticks, a coach lands on « All ».
* UC-5 A professional with no assigned event sees an empty state pointing
  at « All » (not a bare « No events found »).
"""
import json
import urllib.parse
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_calendar_filters_1591 import Calendar1591Common


@tagged('post_install', '-at_install')
class TestMyEventsDefault1730(Calendar1591Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        user_g = env.ref('base.group_user').id
        clinic_user_g = env.ref('bemade_sports_clinic.group_sports_clinic_user').id
        itp_g = env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id
        admin_g = env.ref('bemade_sports_clinic.group_sports_clinic_admin').id
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        Users = env['res.users'].with_context(no_reset_password=True)
        cls.itp = Users.create({
            'name': 'ZZ 1730 Internal TP', 'login': 'zz1730.itp@example.com', 'password': 'zz1730-itp-pass',
            'group_ids': [Command.set([user_g, clinic_user_g, itp_g])],
        })
        cls.cadmin = Users.create({
            'name': 'ZZ 1730 Clinic Admin', 'login': 'zz1730.cadmin@example.com',
            'password': 'zz1730-cadmin-pass', 'group_ids': [Command.set([user_g, admin_g])],
        })
        cls.idle_tp = Users.create({
            'name': 'ZZ 1730 Idle TP', 'login': 'zz1730.idle@example.com', 'password': 'zz1730-idle-pass',
            'group_ids': [Command.set([portal, tp_g])],
        })
        for user in (cls.itp, cls.cadmin, cls.idle_tp):
            env['sports.team.staff'].create({
                'team_id': cls.team_a.id, 'partner_id': user.partner_id.id, 'role': 'therapist'})
        cls.ev_game_a.assigned_staff_ids = [Command.link(cls.itp.id)]

    def setUp(self):
        super().setUp()
        self._switch(True)

    # -- helpers -----------------------------------------------------------
    def _rows(self, tree):
        return {int(i) for i in tree.xpath('//*[@data-pk-section="events.list"]//a/@data-sc-event-id')} & self.ours

    @staticmethod
    def _active_view(tree):
        return tree.xpath('//*[@data-pk-section="events.views"]//a[@aria-pressed="true"]/@data-sc-view')

    @staticmethod
    def _view_href(tree, key):
        return tree.xpath('//*[@data-pk-section="events.views"]//a[@data-sc-view="%s"]/@href' % key)[0]

    @staticmethod
    def _query(url):
        return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))

    @staticmethod
    def _props(tree):
        return json.loads(tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_calendar"]/@props')[0])

    # -- UC-1 --------------------------------------------------------------
    def test_professional_lands_on_my_events(self):
        self._login_tp()
        _text, tree = self._get('/my/events')
        self.assertEqual(self._active_view(tree), ['my'])
        self.assertEqual(self._rows(tree), {self.ev_game_a.id})
        form = tree.xpath('//form[@data-pk-section="events.filters"]')[0]
        self.assertEqual(form.xpath('.//input[@name="view_type"]/@value'), ['my'])
        self.assertEqual(form.xpath('.//select[@name="assigned_user_id"]/option[@selected]/@value'),
                         [str(self.tp.id)])
        # The segments carry the view, so « Past » / « Calendar » stay on it.
        for key in ('upcoming', 'past', 'calendar'):
            href = tree.xpath('//nav[@data-sc-tabs]//a[@data-sc-tab="%s"]/@href' % key)[0]
            self.assertEqual(self._query(href).get('view_type'), 'my', key)
            self.assertEqual(self._query(href).get('assigned_user_id'), str(self.tp.id), key)

    def test_internal_professional_lands_on_my_events(self):
        self.authenticate('zz1730.itp@example.com', 'zz1730-itp-pass')
        _text, tree = self._get('/my/events')
        self.assertEqual(self._active_view(tree), ['my'])
        self.assertEqual(self._rows(tree), {self.ev_game_a.id})

    # -- UC-2 --------------------------------------------------------------
    def test_explicit_all_sticks(self):
        self._login_tp()
        _text, tree = self._get('/my/events')
        all_href = self._view_href(tree, 'all')
        self.assertEqual(self._query(all_href).get('view_type'), 'all')
        _text, tree = self._get(all_href)
        self.assertEqual(self._active_view(tree), ['all'])
        self.assertEqual(self._rows(tree), {self.ev_game_a.id, self.ev_practice_a.id, self.ev_game_c.id})
        form = tree.xpath('//form[@data-pk-section="events.filters"]')[0]
        self.assertEqual(form.xpath('.//input[@name="view_type"]/@value'), ['all'])
        for key in ('upcoming', 'past', 'calendar'):
            href = tree.xpath('//nav[@data-sc-tabs]//a[@data-sc-tab="%s"]/@href' % key)[0]
            self.assertEqual(self._query(href).get('view_type'), 'all', key)
        # A filter that names only a professional (no view) is explicit too.
        _text, tree = self._get('/my/events?assigned_user_id=')
        self.assertEqual(self._active_view(tree), ['all'])

    def test_pager_keeps_the_view(self):
        start = fields.Datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
        self.env['sports.event'].create([{
            'name': 'ZZ 1730 Bulk %03d' % i, 'event_type': 'practice', 'team_ids': [Command.set([self.team_a.id])],
            'date_start': start + timedelta(days=1), 'date_end': start + timedelta(days=1, hours=1),
        } for i in range(81)])
        self._login_tp()
        _text, tree = self._get('/my/events?view_type=all')
        pages = [href for href in tree.xpath('//*[contains(@class, "o_sc_pager")]//a/@href') if '/page/2' in href]
        self.assertTrue(pages)
        self.assertEqual(self._query(pages[0]).get('view_type'), 'all')
        _text, tree = self._get(pages[0])
        self.assertEqual(self._active_view(tree), ['all'])

    # -- UC-3 --------------------------------------------------------------
    def test_coach_and_admin_unchanged(self):
        self._login_coach()
        _text, tree = self._get('/my/events')
        self.assertEqual(self._active_view(tree), ['all'])
        self.assertEqual(self._rows(tree), {self.ev_game_a.id, self.ev_practice_a.id})
        self.authenticate('zz1730.cadmin@example.com', 'zz1730-cadmin-pass')
        _text, tree = self._get('/my/events')
        self.assertEqual(self._active_view(tree), ['all'])
        self.assertEqual(self._rows(tree), {self.ev_game_a.id, self.ev_practice_a.id, self.ev_game_c.id})

    # -- UC-4 --------------------------------------------------------------
    def test_calendar_defaults(self):
        self._login_tp()
        _text, tree = self._get('/my/events/calendar')
        self.assertEqual(self._active_view(tree), ['my'])
        self.assertEqual(self._props(tree)['params'],
                         {'view_type': 'my', 'assigned_user_id': str(self.tp.id)})
        # The view chip is not a filter of the panel's: it stays closed.
        self.assertFalse(tree.xpath('//form[@data-pk-section="events.filters"]//details[@open]'))
        upcoming = tree.xpath('//nav[@data-sc-tabs]//a[@data-sc-tab="upcoming"]/@href')[0]
        self.assertEqual(self._query(upcoming).get('view_type'), 'my')
        # « All » sticks on the calendar too.
        _text, tree = self._get(self._view_href(tree, 'all'))
        self.assertEqual(self._active_view(tree), ['all'])
        self.assertEqual(self._props(tree)['params'], {'view_type': 'all'})
        # Another professional chosen in the panel still opens it.
        _text, tree = self._get('/my/events/calendar?view_type=all&assigned_user_id=%s' % self.itp.id)
        self.assertTrue(tree.xpath('//form[@data-pk-section="events.filters"]//details[@open]'))
        self._login_coach()
        _text, tree = self._get('/my/events/calendar')
        self.assertEqual(self._active_view(tree), ['all'])
        self.assertEqual(self._props(tree)['params'], {})

    # -- UC-5 --------------------------------------------------------------
    def test_empty_my_events_points_at_all(self):
        self.authenticate('zz1730.idle@example.com', 'zz1730-idle-pass')
        _text, tree = self._get('/my/events')
        self.assertEqual(self._active_view(tree), ['my'])
        empty = tree.xpath('//*[@data-pk-section="events.empty_mine"]')
        self.assertEqual(len(empty), 1)
        href = empty[0].xpath('.//a[@data-sc-view-link="all"]/@href')[0]
        self.assertEqual(self._query(href).get('view_type'), 'all')
        # « All » has events: the generic empty state is not shown there.
        _text, tree = self._get(href)
        self.assertFalse(tree.xpath('//*[@data-pk-section="events.empty_mine"]'))
        self.assertTrue(self._rows(tree))
