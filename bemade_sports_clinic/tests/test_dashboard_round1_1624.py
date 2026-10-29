"""Task 1624 — owner UAT round 1 (2026-10-29) on the app dashboard.
Synthetic fixtures only (dashboard_common_1624; this repository is public).

Acceptance criteria:

* UC-R1 Coach wording: for a coach the « Couvertures à venir » section is
  titled « Événements à venir » (its empty state speaks of events too); a
  therapist keeps « Couvertures à venir »; a custom title still wins.
* UC-R2 À faire for a coach: the « Retours dépassés » line is a therapist
  line (they update those dates); a coach keeps only the activity lines.
* UC-R3 Default order: Aujourd'hui, Indicateurs, À faire, Changements
  récents, Joueurs à surveiller, Joueurs que je suis, Annonces,
  Couvertures / Événements à venir, then « Feuilles de temps manquantes »
  (therapists). A saved layout keeps its order; « Rétablir » gives the new
  one.
* UC-R4 À faire fold-outs: each line opens inline into its cards — the
  activity cards of the Activités page (with their Fait / Reprogrammer
  sheets on the page), the injury cards, the player cards; 8 cards, the
  others under « Voir les N autres ».
* UC-R5 Event « Détails »: each event of Aujourd'hui and Couvertures à
  venir folds out its details (time span, coverage time, venue, teams,
  assigned staff, description) and keeps its link to the event.
* UC-R6 « Feuilles de temps manquantes » (therapists only): my past
  assigned events with no timesheet of mine (the events page's « missing
  timesheets » predicate), never a cancelled one, within the « days back »
  setting and the « Portée »; each card's « Ajouter ma feuille de temps »
  opens the event page with its add-timesheet sheet open.
* UC-R7 « Suivre »: a user follows / unfollows a player they can read (a
  fetch POST, no reload); an unreadable player cannot be followed; my
  follows are mine only (another user never sees them, not even over
  RPC); the toggle is on the player card's « Détails » and the player page
  header; the « Joueurs que je suis » widget lists my followed players
  (full cards) and takes the « Portée ».
"""
import json
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.models import sc_dashboard
from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK
from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common, _player

TP_ORDER = ['today', 'indicators', 'todo', 'recent_changes', 'watch', 'followed',
            'announcements', 'coverage', 'missing_timesheets']
COACH_ORDER = [key for key in TP_ORDER if key != 'missing_timesheets']
XHR = {'X-Requested-With': 'XMLHttpRequest'}


@tagged('post_install', '-at_install')
class TestDashboardRound1_1624(Dashboard1624Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        now = fields.Datetime.now()

        def _event(name, days_ago, teams, state='confirmed', **extra):
            start = now - timedelta(days=days_ago)
            return env['sports.event'].create(dict({
                'name': name, 'event_type': 'game',
                'date_start': start, 'date_end': start + timedelta(hours=2),
                'team_ids': [Command.set(teams.ids)],
                'assigned_staff_ids': [Command.set(cls.tp.ids)],
                'state': state,
            }, **extra))

        cls.ev_missing = _event('DB Missing A', 3, cls.team_a)
        cls.ev_missing_c = _event('DB Missing C', 2, cls.team_c)
        cls.ev_missing_old = _event('DB Missing Old', 50, cls.team_a)
        cls.ev_missing_cancelled = _event('DB Missing Cancelled', 4, cls.team_a, state='cancelled')
        cls.ev_done = _event('DB Done A', 5, cls.team_a)
        env['sports.event.timesheet'].create({'event_id': cls.ev_done.id, 'user_id': cls.tp.id})

    def _xhr_post(self, url, data):
        data = dict(data, csrf_token=self._csrf())
        return self.url_open(url, data=data, headers=XHR, allow_redirects=False)

    def _title(self, tree, instance_id):
        node = self._section(tree, instance_id).xpath('.//*[contains(@class, "o_sc_dw_title_text")]')[0]
        return node.text_content().strip()

    # -- UC-R1 ---------------------------------------------------------------
    def test_coach_coverage_wording(self):
        self._login_coach()
        _text, tree = self._get('/my/home')
        self.assertEqual(self._title(tree, 'coverage'), 'Upcoming events')
        self._login_tp()
        _text, tree = self._get('/my/home')
        self.assertEqual(self._title(tree, 'coverage'), 'Upcoming coverage')
        # The empty state follows the role.
        self._dash(self.tp)._sc_layout_update('coverage', settings={'scope_team_ids': [self.team_c.id], 'days': 7})
        _text, tree = self._get('/my/home')
        self.assertIn('No upcoming coverage', self._section(tree, 'coverage').text_content())
        # A custom title still wins.
        self._dash(self.coach)._sc_layout_update('coverage', title='Synthetic games')
        self._login_coach()
        _text, tree = self._get('/my/home')
        self.assertEqual(self._title(tree, 'coverage'), 'Synthetic games')
        # The Configurer page names it the same way.
        _text, tree = self._get('/my/app/dashboard/configure')
        self.assertIn('Upcoming events', tree.xpath('//*[@data-sc-dash-item="coverage"]')[0].text_content())

    # -- UC-R2 ---------------------------------------------------------------
    def test_coach_todo_lines(self):
        self.assertEqual(self._dash(self.coach)._sc_todo_kinds(), ['activities'])
        self.assertEqual(self._dash(self.tp)._sc_todo_kinds(), list(sc_dashboard.TODO_KINDS))
        self.shared.sudo().with_context(**{PAST_RETURN_OK: True}).write(
            {'predicted_return_date': fields.Date.today() - timedelta(days=2)})
        self._login_coach()
        _text, tree = self._get('/my/home')
        self.assertFalse(self._section(tree, 'todo').xpath('.//*[@data-sc-todo="returns"]'))

    # -- UC-R3 ---------------------------------------------------------------
    def test_default_order(self):
        self.assertEqual([i['id'] for i in self._dash(self.tp)._sc_layout()], TP_ORDER)
        self.assertEqual([i['id'] for i in self._dash(self.coach)._sc_layout()], COACH_ORDER)
        # A saved (round-0) layout keeps its order; the new widgets join at the end.
        old = ['today', 'todo', 'recent_changes', 'watch', 'announcements', 'indicators', 'coverage']
        self.tp.sudo().sc_dashboard_layout = {'v': 1, 'instances': [
            {'id': key, 'widget': key, 'enabled': True, 'settings': {}} for key in old]}
        ids = [i['id'] for i in self._dash(self.tp)._sc_layout()]
        self.assertEqual(ids[:7], old)
        self.assertEqual(sorted(ids[7:]), ['followed', 'missing_timesheets'])
        self._dash(self.tp)._sc_layout_reset()
        self.assertEqual([i['id'] for i in self._dash(self.tp)._sc_layout()], TP_ORDER)

    # -- UC-R4 ---------------------------------------------------------------
    def test_todo_activity_cards(self):
        model = self.env['ir.model']._get('sports.patient').id
        today = fields.Date.context_today(self.tp)
        for n in range(10):
            self.env['mail.activity'].create({
                'res_model_id': model, 'res_id': self.red.id, 'user_id': self.tp.id,
                'summary': 'Synthetic overdue %s' % n, 'date_deadline': today - timedelta(days=1)})
        self.env['mail.activity'].create({
            'res_model_id': model, 'res_id': self.red.id, 'user_id': self.tp.id,
            'summary': 'Synthetic due today', 'date_deadline': today})
        self._login_tp()
        _text, tree = self._get('/my/home')
        todo = self._section(tree, 'todo')
        overdue = todo.xpath('.//details[@data-sc-todo="activities_overdue"]')
        self.assertEqual(len(overdue), 1)
        rows = overdue[0].xpath('.//*[@data-sc-activity-row]')
        self.assertGreaterEqual(len(rows), 10)
        # 8 shown, the others folded.
        folded = overdue[0].xpath('.//details[@data-sc-dw-more]//*[@data-sc-activity-row]')
        self.assertEqual(len(rows) - len(folded), 8)
        # The activity cards' actions and the sheets they open.
        self.assertTrue(overdue[0].xpath('.//button[@data-sc-action="activity.complete"]'))
        self.assertTrue(overdue[0].xpath('.//button[@data-sc-action="activity.reschedule"]'))
        for sheet in ('sc_activity_complete_sheet', 'sc_activity_reschedule_sheet'):
            self.assertEqual(len(tree.xpath('//dialog[@id="%s"]' % sheet)), 1, sheet)
        self.assertEqual(tree.xpath('//dialog[@id="sc_activity_complete_sheet"]'
                                    '//input[@name="return_url"]/@value'), ['/my/home'])
        due = todo.xpath('.//details[@data-sc-todo="activities_today"]')[0]
        self.assertIn('Synthetic due today', due.text_content())

    def test_todo_injury_and_player_cards(self):
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.yellow.id, 'diagnosis': 'Synthetic tweak'})
        injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
        self.red.sudo().write({'pending_removal': True, 'pending_removal_team_id': self.team_a.id})
        self.shared.sudo().with_context(**{PAST_RETURN_OK: True}).write(
            {'predicted_return_date': fields.Date.today() - timedelta(days=2)})
        self._login_tp()
        _text, tree = self._get('/my/home')
        todo = self._section(tree, 'todo')
        verify = todo.xpath('.//details[@data-sc-todo="verify"]')[0]
        cards = verify.xpath('.//details[@data-sc-edit-card="injury"]')
        self.assertEqual([int(c.get('data-sc-injury-id')) for c in cards], [injury.id])
        # The injury card's quick « Verify ».
        self.assertTrue(verify.xpath('.//button[@data-sc-injury-quick="verify"]'))
        removals = todo.xpath('.//details[@data-sc-todo="removals"]')[0]
        self.assertEqual([int(i) for i in removals.xpath('.//*[@data-sc-player-id]/@data-sc-player-id')],
                         [self.red.id])
        returns = todo.xpath('.//details[@data-sc-todo="returns"]')[0]
        self.assertEqual([int(i) for i in returns.xpath('.//*[@data-sc-player-id]/@data-sc-player-id')],
                         [self.shared.id])
        # The player cards keep their lazy « Details ».
        self.assertTrue(returns.xpath('.//*[@data-sc-row-expand]'))
        # Unique ids on the page.
        ids = tree.xpath('//@id')
        self.assertEqual(len(ids), len(set(ids)), [i for i in ids if ids.count(i) > 1])

    # -- UC-R5 ---------------------------------------------------------------
    def test_event_details_fold_out(self):
        self.ev_soon.write({'description': '<p>Synthetic bring the tape</p>',
                            'therapist_start': self.ev_soon.date_start - timedelta(hours=1),
                            'therapist_end': self.ev_soon.date_end})
        self._login_tp()
        _text, tree = self._get('/my/home')
        for instance_id, event in (('coverage', self.ev_soon), ('today', self.ev_today)):
            section = self._section(tree, instance_id)
            details = section.xpath('.//details[@data-sc-event-details="%s"]' % event.id)
            self.assertEqual(len(details), 1, instance_id)
            fields_shown = details[0].xpath('.//*[@data-sc-ev-field]/@data-sc-ev-field')
            for key in ('when', 'teams', 'staff'):
                self.assertIn(key, fields_shown, (instance_id, key))
            self.assertIn('PC TP', details[0].text_content())
            self.assertIn('PC Team A', details[0].text_content())
            # The link to the event stays.
            self.assertTrue(section.xpath('.//a[contains(@href, "/my/event/%s")]' % event.id))
        coverage = self._section(tree, 'coverage').xpath(
            './/details[@data-sc-event-details="%s"]' % self.ev_soon.id)[0]
        self.assertIn('Synthetic bring the tape', coverage.text_content())
        self.assertIn('coverage', coverage.xpath('.//*[@data-sc-ev-field]/@data-sc-ev-field'))

    # -- UC-R6 ---------------------------------------------------------------
    def _missing_ids(self, tree):
        # The fixtures' past events only (today's game, already started or
        # not, depends on the clock).
        mine = set((self.ev_missing | self.ev_missing_c | self.ev_missing_old
                    | self.ev_missing_cancelled | self.ev_done | self.event).ids)
        return [int(i) for i in self._section(tree, 'missing_timesheets').xpath(
            './/*[@data-sc-event-id]/@data-sc-event-id') if int(i) in mine]

    def test_missing_timesheets_widget(self):
        self.assertNotIn('missing_timesheets', [s['key'] for s in self._dash(self.coach)._sc_widgets()])
        self._login_tp()
        _text, tree = self._get('/my/home')
        # Default 30 days back, newest first; my timesheet / cancelled / older never.
        self.assertEqual(self._missing_ids(tree), [self.ev_missing_c.id, self.ev_missing.id])
        add = self._section(tree, 'missing_timesheets').xpath(
            './/a[@data-sc-action="dashboard.timesheet.add"]/@href')
        self.assertIn('/my/event/%s?add_timesheet=1' % self.ev_missing.id, ' '.join(add))
        # Days back.
        self._dash(self.tp)._sc_layout_update('missing_timesheets', settings={'days_back': 60})
        _text, tree = self._get('/my/home')
        self.assertIn(self.ev_missing_old.id, self._missing_ids(tree))
        # Portée.
        self._dash(self.tp)._sc_layout_update(
            'missing_timesheets', settings={'scope_team_ids': [self.team_c.id], 'days_back': 30})
        _text, tree = self._get('/my/home')
        self.assertEqual(self._missing_ids(tree), [self.ev_missing_c.id])
        # Same predicate as the events page's « missing timesheets » segment.
        Event = self.env['sports.event'].with_user(self.tp)
        same = Event.search(Event._sc_missing_timesheet_domain(self.tp))
        self.assertIn(self.ev_missing, same)
        self.assertNotIn(self.ev_done, same)
        # A coach never gets the section.
        self._login_coach()
        _text, tree = self._get('/my/home')
        self.assertFalse(tree.xpath('//section[@data-sc-widget="missing_timesheets"]'))
        with self.assertRaises(Exception):
            self._dash(self.coach)._sc_layout_add('missing_timesheets')

    def test_add_timesheet_deep_link_opens_sheet(self):
        self._login_tp()
        _text, tree = self._get('/my/event/%s?add_timesheet=1' % self.ev_missing.id)
        self.assertTrue(tree.xpath('//dialog[@id="sc_ts_add_sheet"][@data-sc-sheet-open-on-load="1"]'))
        _text, tree = self._get('/my/event/%s' % self.ev_missing.id)
        self.assertTrue(tree.xpath('//dialog[@id="sc_ts_add_sheet"]'))
        self.assertFalse(tree.xpath('//dialog[@id="sc_ts_add_sheet"][@data-sc-sheet-open-on-load]'))

    # -- UC-R7 ---------------------------------------------------------------
    def test_follow_and_unfollow(self):
        self._login_tp()
        resp = self._xhr_post('/my/player/%s/follow' % self.red.id, {'follow': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.text), {'ok': True, 'followed': True})
        self.assertEqual(self.tp.sudo().sc_followed_patient_ids, self.red)
        self.assertTrue(self.red.with_user(self.tp).sc_followed_by_me)
        resp = self._xhr_post('/my/player/%s/follow' % self.red.id, {'follow': '0'})
        self.assertEqual(json.loads(resp.text), {'ok': True, 'followed': False})
        self.assertFalse(self.tp.sudo().sc_followed_patient_ids)

    def test_cannot_follow_unreadable_player(self):
        # The coach staffs Team A and Team C: Pat Two (Team B) is not theirs.
        with self.assertRaises(AccessError):
            self.player_b.with_user(self.coach).check_access('read')
        with self.assertRaises(AccessError):
            self.env['sports.patient'].with_user(self.coach).browse(self.player_b.id)._sc_follow(True)
        self._login_coach()
        with mute_logger('odoo.http'):
            resp = self._xhr_post('/my/player/%s/follow' % self.player_b.id, {'follow': '1'})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(self.coach.sudo().sc_followed_patient_ids)

    def test_follows_are_private(self):
        self.red.with_user(self.tp)._sc_follow(True)
        # The coach (who reads Red too) does not see my follow.
        self.assertFalse(self.red.with_user(self.coach).sc_followed_by_me)
        self.assertFalse(self._dash(self.coach)._sc_data_followed(self.env['sports.team'], False))
        # Nor over RPC: the relation is not readable by another user.
        with self.assertRaises(AccessError):
            self.tp.with_user(self.coach).read(['sc_followed_patient_ids'])
        with self.assertRaises(AccessError):
            self.tp.with_user(self.tp).read(['sc_followed_patient_ids'])
        # Nor can anyone write another user's follows.
        with self.assertRaises(AccessError):
            self.tp.with_user(self.coach).write({'sc_followed_patient_ids': [Command.set([])]})

    def test_follow_toggle_on_cards_and_player_page(self):
        self.red.with_user(self.tp)._sc_follow(True)
        self._login_tp()
        _text, tree = self._get('/my/player/%s/row-detail' % self.red.id)
        self.assertEqual(tree.xpath('//button[@data-sc-follow="%s"]/@data-sc-followed' % self.red.id), ['1'])
        _text, tree = self._get('/my/player/%s/row-detail' % self.shared.id)
        self.assertEqual(tree.xpath('//button[@data-sc-follow="%s"]/@data-sc-followed' % self.shared.id), ['0'])
        _text, tree = self._get('/my/player?player_id=%s' % self.red.id)
        self.assertEqual(tree.xpath('//*[@data-sc-section="player.hero"]'
                                    '//button[@data-sc-follow="%s"]/@data-sc-followed' % self.red.id), ['1'])

    def test_followed_widget(self):
        self.red.with_user(self.tp)._sc_follow(True)
        self.yellow.with_user(self.tp)._sc_follow(True)
        other = _player(self.env, 'Calm', 'Synth', self.team_a)
        other.with_user(self.coach)._sc_follow(True)
        self._login_tp()
        _text, tree = self._get('/my/home')
        section = self._section(tree, 'followed')
        ids = [int(i) for i in section.xpath('.//*[@data-sc-player-id]/@data-sc-player-id')]
        self.assertEqual(sorted(ids), sorted((self.red | self.yellow).ids))
        # Full cards: the lazy « Details ».
        self.assertTrue(section.xpath('.//*[@data-sc-row-expand]'))
        # Portée.
        self._dash(self.tp)._sc_layout_update('followed', settings={'scope_team_ids': [self.team_c.id]})
        _text, tree = self._get('/my/home')
        section = self._section(tree, 'followed')
        self.assertEqual([int(i) for i in section.xpath('.//*[@data-sc-player-id]/@data-sc-player-id')],
                         [self.yellow.id])
        # Nothing followed: an empty state, not the « no team » hint.
        self._login_coach()
        self.env['res.users'].browse(self.coach.id).sudo().sc_followed_patient_ids = False
        _text, tree = self._get('/my/home')
        section = self._section(tree, 'followed')
        self.assertFalse(section.xpath('.//*[@data-sc-player-id]'))
        self.assertIn('You do not follow any player yet', section.text_content())
