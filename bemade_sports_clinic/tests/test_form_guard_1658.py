"""Task 1658 — the app-wide form rule. Synthetic fixtures only.

Rule (owner, #1655 review): a form's primary action is disabled
(aria-disabled + aria-describedby) with a short reason line until it can
succeed; a server refusal is shown inside the form, the values kept, no
redirect away. Never a button that silently does nothing.

Acceptance criteria covered here:

* AC-1 Every submit form of the app shell is guarded (data-sc-guard) and
  keeps its POST contract (same action, same field names); the shared texts
  (« Complete: », the generic error) are rendered once by the layout; the
  #1655 panel uses the shared guard (its own data attributes kept).
* AC-2 A guarded form's fetch (X-Sc-Guard) never consumes the pending
  session toast: the real navigation that follows still shows it.
* AC-3 (tours, phone) contact, timesheet, injury, event create,
  announcement, activity reassign: greyed with a reason → ready when valid →
  a forced server refusal shows in the form, values kept, same page (and a
  valid contact / announcement goes through).
"""
from datetime import datetime, timedelta

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


class Guard1658Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start = datetime(2026, 3, 3, 10, 0)
        cls.clinic_event = cls.env['sports.event'].create({
            'name': 'G1658 Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        cls.team_a.with_user(cls.tp).write({'announcement': False})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _tree(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return lxml_html.fromstring(resp.text)


@tagged('post_install', '-at_install')
class TestFormGuard1658(Guard1658Common):

    # -- AC-1 -------------------------------------------------------------
    def test_forms_are_guarded_with_their_contract(self):
        self._login_tp()
        expectations = {
            '/my/player?player_id=%s&tab=info' % self.player.id: {
                '/my/player/contact/save': ('fetch', {'name', 'contact_type', 'mobile', 'email', 'patient_id'}),
                '/my/patient/injury/create': ('fetch', {'diagnosis', 'patient_id'}),
                '/my/injury/note/add': ('fetch', {'patient_id', 'injury_id'}),
                '/my/activity/save': ('fetch', {'summary', 'date_deadline', 'user_id', 'activity_type_id'}),
            },
            '/my/activities': {
                '/my/activity/complete': ('fetch', {'activity_id', 'feedback'}),
                '/my/activity/reschedule': ('fetch', {'activity_id', 'new_deadline'}),
                '/my/activity/reassign': ('fetch', {'activity_id', 'new_user_id'}),
                '/my/activity/cancel': ('fetch', {'activity_id'}),
            },
            '/my/event/%s' % self.clinic_event.id: {
                '/my/event/%s/timesheet/add' % self.clinic_event.id: (
                    'fetch', {'travel_start', 'coverage_start', 'coverage_end', 'travel_end'}),
                '/my/event/%s/cancel' % self.clinic_event.id: ('fetch', {'cancel_reason'}),
            },
            '/my/event/create': {
                '/my/event/create/submit': ('fetch', {'name', 'date_start', 'date_end', 'team_ids'}),
            },
            '/my/team?team_id=%s' % self.team_a.id: {
                '/my/team/%s/announcement' % self.team_a.id: ('fetch', set()),
            },
            '/my/notepad': {
                '/my/notepad/add': ('fetch', set()),
            },
        }
        for page, forms in expectations.items():
            tree = self._tree(page)
            self.assertTrue(tree.xpath('//*[@data-sc-guard-texts][@data-missing][@data-generic]'), page)
            for action, (mode, names) in forms.items():
                found = [f for f in tree.xpath('//form[@data-sc-guard]') if (f.get('action') or '').split('?')[0] == action]
                self.assertTrue(found, (page, action))
                form = found[0]
                self.assertEqual(form.get('data-sc-guard-mode') or 'native', mode, (page, action))
                self.assertEqual(form.get('method'), 'post', action)
                present = set(form.xpath('.//*[@name]/@name'))
                self.assertTrue(names <= present, (action, names - present))
                self.assertTrue(form.xpath('.//*[@data-sc-guard-reason][@id]'), action)
                self.assertTrue(form.xpath('.//*[@data-sc-guard-error]'), action)
        # The #1655 panel: on the shared guard, its own attributes kept.
        tree = self._tree('/my/players?add=1')
        panel = tree.xpath('//form[@data-sc-player-add][@data-sc-guard]')
        self.assertTrue(panel)
        self.assertTrue(panel[0].xpath('.//button[@data-sc-player-add-submit][@data-sc-guard-submit]'))
        self.assertTrue(panel[0].xpath('.//*[@data-sc-player-add-reason][@data-sc-guard-reason]'))

    # -- AC-2 -------------------------------------------------------------
    def test_guard_probe_keeps_the_session_toast(self):
        self._login_tp()
        # A POST that leaves a session toast: the removal request of a
        # coach-like flow is not available to a therapist; use the player
        # undo refusal path's sibling — the announcement restore refusal.
        self.url_open('/my/team/%s/announcement/restore' % self.team_a.id,
                      data={'csrf_token': self._csrf()}, allow_redirects=False)
        url = '/my/team?team_id=%s' % self.team_a.id
        probe = self.url_open(url, headers={'X-Sc-Guard': '1'})
        tree = lxml_html.fromstring(probe.text)
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_toast")][@data-sc-notify]'), 'the probe sees it')
        tree = self._tree(url)
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_toast")][@data-sc-notify]'), 'the real page still shows it')
        tree = self._tree(url)
        self.assertFalse(tree.xpath('//*[contains(@class, "o_sc_toast")][@data-sc-notify]'), 'shown once')


@tagged('post_install', '-at_install')
class TestFormGuardTours1658(Guard1658Common):
    browser_size = '390x844'

    def test_contact(self):
        before = len(self.player.contact_ids)
        self.start_tour('/my/player?player_id=%s&tab=info' % self.player.id, 'sc_1658_contact',
                        login='pc.tp@example.com')
        self.assertEqual(len(self.player.contact_ids), before + 1)
        self.assertEqual(self.player.contact_ids.sorted('id')[-1].name, 'Synthetic Parent')

    def test_timesheet(self):
        Timesheet = self.env['sports.event.timesheet']
        self.start_tour('/my/event/%s' % self.clinic_event.id, 'sc_1658_timesheet', login='pc.tp@example.com')
        self.assertFalse(Timesheet.search_count([('event_id', '=', self.clinic_event.id)]))

    def test_injury(self):
        self.start_tour('/my/player?player_id=%s&tab=injuries' % self.player.id, 'sc_1658_injury',
                        login='pc.tp@example.com')
        self.assertFalse(self.env['sports.patient.injury'].search_count([('diagnosis', '=', 'Synthetic sprain 1658')]))

    def test_event_create(self):
        self.start_tour('/my/event/create', 'sc_1658_event', login='pc.tp@example.com')
        self.assertFalse(self.env['sports.event'].search_count([('name', '=', 'Synthetic game 1658')]))

    def test_announcement(self):
        self.start_tour('/my/team?team_id=%s' % self.team_a.id, 'sc_1658_announcement', login='pc.tp@example.com')
        self.assertEqual(self.team_a.announcement, 'Synthetic bus at 7 (1658)')

    def test_activity_reassign(self):
        self.start_tour('/my/activities?x1658=%s' % self.plain.id, 'sc_1658_activity', login='pc.tp@example.com')
        self.assertEqual(self.act_player.user_id, self.tp)
