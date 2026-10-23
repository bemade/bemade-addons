"""Task 1611 — event, timesheet, activity and notepad saves refresh what
depends on them (read fragments). Synthetic fixtures only.

Use case: a therapist edits an event, one of their timesheets, an activity or
a notepad note in place; the page's titles, chips, read lines, banners and
lists show the saved data at once.

Acceptance criteria:

* AC-E1 Event name -> app bar title, crumb, document title.
* AC-E2 Event type -> the kind chip; start / end and therapist times -> the
  « When » / « Therapist » rows of the read view.
* AC-E3 Assigned staff -> the staff list, « Add My Timesheet » (app bar
  action + its sheet) and the « Missing timesheets » banner (admin view).
* AC-E4 Timesheet times -> the card's « when » and its read lines with the
  travel / coverage totals (event page and /my/sc/timesheets); grouped by
  date, the list fragment moves the card to its new date group.
* AC-E5 Activity due date -> the state chip (« Overdue »); summary -> the app
  bar title; note -> the note block; the save asks for the live counters
  (overdue badge).
* AC-E6 Notepad: text / links -> the card's text and link chips; the player
  chip reads « Last, First » like the pencil card's choice and its save.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon, FragmentsMixin
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_event_timesheets_1584 import EventTimesheets1584Common


@tagged('post_install', '-at_install')
class TestFragmentsEvent1611(FragmentsCommon):

    def setUp(self):
        super().setUp()
        # A wide travel window: the coverage times below stay inside it.
        self.timesheet.write({
            'travel_start': '2026-02-01 06:00:00', 'coverage_start': '2026-02-02 08:00:00',
            'coverage_end': '2026-02-05 12:00:00', 'travel_end': '2026-02-06 20:00:00',
        })

    def _url(self):
        return '/my/event/%s' % self.event.id

    def _ekey(self, part):
        return 'sports.event:%s:%s' % (self.event.id, part)

    def _tkey(self, part):
        return 'sports.event.timesheet:%s:%s' % (self.timesheet.id, part)

    @staticmethod
    def _rows(node):
        return {' '.join(dt.itertext()).strip(): ' '.join(' '.join(dd.itertext()).split())
                for dt, dd in zip(node.xpath('.//dt'), node.xpath('.//dd'))}

    # -- AC-E1 -------------------------------------------------------------
    def test_name_refreshes_title(self):
        self._login_tp()
        payload = self._saved(self.event, 'name', 'Synthetic Final')
        for part in ('appbar', 'crumb'):
            self.assertRefreshes(payload, self._ekey(part))
        answer = self._fragments(self._url(), [self._ekey('appbar'), self._ekey('crumb')])
        self.assertIn('Synthetic Final', answer['title'])
        for part in ('appbar', 'crumb'):
            self.assertIn('Synthetic Final', answer['fragments'][self._ekey(part)])

    # -- AC-E2 -------------------------------------------------------------
    def test_type_and_times_refresh_chips_and_read_view(self):
        self._login_tp()
        payload = self._saved(self.event, 'event_type', 'practice')
        self.assertRefreshes(payload, self._ekey('chips'))
        kinds = dict(self.env['sports.event']._fields['event_type']._description_selection(self.env))
        chips = self._fragment(self._url(), self._ekey('chips'))
        self.assertIn(kinds['practice'], self._text(chips))
        payload = self._saved(self.event, 'date_start', '2026-02-02T08:15')
        self.assertRefreshes(payload, self._ekey('read'))
        self._saved(self.event, 'therapist_start', '2026-02-02T07:45')
        self._saved(self.event, 'therapist_end', '2026-02-02T13:05')
        rows = self._rows(self._fragment(self._url(), self._ekey('read')))
        self.assertIn('08:15', rows['When'])
        self.assertIn('07:45', rows['Therapist'])
        self.assertIn('13:05', rows['Therapist'])
        self.assertFragmentMatchesPage(self._url(), self._ekey('read'))

    # -- AC-E3 -------------------------------------------------------------
    def test_staff_refreshes_list_and_add_timesheet(self):
        self._login_tp()
        payload = self._saved(self.event, 'assigned_staff_ids', '')
        # Task 1607 (deliberate update): « Add My Timesheet » left the app
        # bar (« :action ») for the timesheets list header (« :ts-head »).
        for part in ('read', 'ts-head', 'ts-add'):
            self.assertRefreshes(payload, self._ekey(part))
        answer = self._fragments(self._url(), [self._ekey('ts-head'), self._ekey('ts-add'), self._ekey('read')])
        self.assertNotIn('timesheet.add', answer['fragments'][self._ekey('ts-head')])
        self.assertNotIn('<dialog', answer['fragments'][self._ekey('ts-add')])
        self.assertNotIn('PC TP', answer['fragments'][self._ekey('read')])
        self._saved(self.event, 'assigned_staff_ids', str(self.tp.id))
        answer = self._fragments(self._url(), [self._ekey('ts-head'), self._ekey('ts-add'), self._ekey('read')])
        self.assertIn('data-sc-action="timesheet.add"', answer['fragments'][self._ekey('ts-head')])
        self.assertIn('sc_ts_add_sheet', answer['fragments'][self._ekey('ts-add')])
        self.assertIn('PC TP', answer['fragments'][self._ekey('read')])
        self.assertFragmentMatchesPage(self._url(), self._ekey('ts-add'))

    # -- AC-E4 -------------------------------------------------------------
    def test_timesheet_times_refresh_card(self):
        self._login_tp()
        payload = self._saved(self.timesheet, 'coverage_start', '2026-02-02T09:00')
        payload = self._saved(self.timesheet, 'coverage_end', '2026-02-02T11:30')
        for part in ('head', 'read'):
            self.assertRefreshes(payload, self._tkey(part))
        self.assertRefreshes(payload, self._ekey('timesheets'))
        for url in (self._url(), '/my/sc/timesheets'):
            read = self._fragment(url, self._tkey('read'))
            self.assertEqual(self._rows(read)['Coverage Hours'], '2:30', url)
            head = self._fragment(url, self._tkey('head'))
            self.assertIn('09:00', self._text(head), url)
            self.assertFragmentMatchesPage(url, self._tkey('read'))

    def test_timesheet_moves_to_its_date_group(self):
        self._login_tp()
        self._saved(self.timesheet, 'coverage_start', '2026-02-02T09:00')
        url = '/my/sc/timesheets?group_by=date'
        key = 'page:timesheets:list'

        def group_of_card():
            node = self._fragment(url, key)
            self.assertEqual(node.get('data-sc-fragment-mode'), 'list')
            card = node.xpath('.//*[@data-sc-fragment-item="%s"]' % self._tkey('card'))[0]
            group = card.xpath('ancestor::*[@data-sc-group][1]')[0]
            return self._text(group.xpath('./h3')[0])
        self.assertEqual(group_of_card(), '2026-02-02')
        payload = self._saved(self.timesheet, 'coverage_start', '2026-02-05T09:00')
        self.assertRefreshes(payload, key)
        self.assertEqual(group_of_card(), '2026-02-05')

    # -- AC-E5 -------------------------------------------------------------
    def test_activity_refreshes_chip_title_note_and_badge(self):
        self._login_tp()
        url = '/my/activity/%s' % self.act_player.id
        akey = 'mail.activity:%s:%%s' % self.act_player.id
        past = fields.Date.to_string(fields.Date.today() - timedelta(days=3))
        payload = self._saved(self.act_player, 'date_deadline', past)
        self.assertTrue(payload['live_counts'])
        for part in ('chips', 'read', 'appbar'):
            self.assertRefreshes(payload, akey % part)
        chips = self._fragment(url, akey % 'chips')
        self.assertIn('Overdue', self._text(chips))
        self._saved(self.act_player, 'summary', 'Synthetic follow-up')
        self._saved(self.act_player, 'note', 'Synthetic note body')
        answer = self._fragments(url, [akey % 'appbar', akey % 'read'])
        self.assertIn('Synthetic follow-up', answer['title'])
        self.assertIn('Synthetic follow-up', answer['fragments'][akey % 'appbar'])
        self.assertIn('Synthetic note body', answer['fragments'][akey % 'read'])
        count = self.url_open('/my/activities/overdue/count').json()['count']
        self.assertGreaterEqual(count, 1)

    # -- AC-E6 -------------------------------------------------------------
    def test_notepad_chips_follow_links(self):
        self.player.write({'jersey_number': '9'})
        note = self.env['sports.quick.note'].create({'note': 'Synthetic jot', 'user_id': self.tp.id})
        self._login_tp()
        key = 'sports.quick.note:%s:read' % note.id
        payload = self._saved(note, 'patient_id', str(self.player.id))
        self.assertRefreshes(payload, key)
        read = self._fragment('/my/notepad', key)
        chips = [self._text(chip) for chip in read.xpath('.//span[contains(concat(" ", @class, " "), " o_sc_chip ")]')]
        self.assertEqual(chips, [self.player._portal_list_name()])
        self.assertEqual(payload['display'], self.player._portal_list_name())
        self._saved(note, 'note', 'Synthetic jot, edited')
        read = self._fragment('/my/notepad', key)
        self.assertIn('Synthetic jot, edited', self._text(read))


@tagged('post_install', '-at_install')
class TestFragmentsMissingTimesheets1611(FragmentsMixin, EventTimesheets1584Common):

    def setUp(self):
        super().setUp()
        self._switch(True)

    # -- AC-E3 (admin view) ------------------------------------------------
    def test_staff_refreshes_missing_banner(self):
        key = 'sports.event:%s:missing' % self.event.id
        url = '/my/event/%s' % self.event.id
        self.authenticate('p77.cadmin@example.com', 'p77-cadmin-pass')
        banner = self._fragment(url, key)
        self.assertIn('P77 Internal TP', self._text(banner))
        self._login_tp()
        payload = self._saved(self.event, 'assigned_staff_ids', ','.join(
            str(uid) for uid in (self.tp.id, self.tp2.id)))
        self.assertRefreshes(payload, key)
        self.authenticate('p77.cadmin@example.com', 'p77-cadmin-pass')
        banner = self._fragment(url, key)
        self.assertNotIn('P77 Internal TP', self._text(banner))
        self.assertFalse(banner.xpath('.//*[contains(@class, "o_sc_banner")]'))
