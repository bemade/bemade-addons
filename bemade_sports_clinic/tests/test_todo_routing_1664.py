"""Task 1664 — To-Do routing gaps and hard-to-reach actions. Synthetic
fixtures only.

Acceptance criteria covered here:

* AC-1 Routing (« Vérifier la blessure », « Compléter la fiche »), ONE helper
  (``sports.patient._sc_todo_route``): the player's teams, the reporter's
  teams first, then the others by id; within a team the head therapist,
  then any therapist with a user account; nobody → the first clinic
  administrator. A multi-team player whose first team has no therapist
  account gets a To-Do from the second team's therapist; one To-Do only.
* AC-2 The notepad reminder (« Stale quick note ») shows in « Mes
  activités » for the note's owner (with a link to the notepad), never for
  another therapist; the overdue clock counts it.
* AC-3 « Réassigner » is offered on the player Activités tab, « Mes
  activités » and the activity page.
* AC-4 A coach on two teams of the same player sees « Demander le retrait »
  on the player page opened from the Joueurs list (no team context); the
  sheet asks « Which team? », a request without a team is refused, with a
  team it goes through.
"""
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


class Routing1664Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id

        def _user(login, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': login.split('@')[0], 'login': login, 'password': login,
                'group_ids': [Command.set(groups)]})

        cls.tp_second = _user('r1664.second@example.com', [portal, tp_g])
        cls.tp_head = _user('r1664.head@example.com', [portal, tp_g])
        cls.coach2 = _user('r1664.coach@example.com', [portal, coach_g])
        # Team 1: no therapist account (a coach only); team 2: a therapist.
        cls.team_1 = env['sports.team'].create({'name': 'R1664 Team One'})
        cls.team_2 = env['sports.team'].create({'name': 'R1664 Team Two'})
        cls.team_3 = env['sports.team'].create({'name': 'R1664 Team Three'})
        Staff = env['sports.team.staff']
        Staff.create({'team_id': cls.team_1.id, 'partner_id': cls.coach2.partner_id.id, 'role': 'coach'})
        Staff.create({'team_id': cls.team_2.id, 'partner_id': cls.coach2.partner_id.id, 'role': 'coach'})
        Staff.create({'team_id': cls.team_2.id, 'partner_id': cls.tp_second.partner_id.id, 'role': 'therapist'})
        Staff.create({'team_id': cls.team_3.id, 'partner_id': cls.tp_second.partner_id.id, 'role': 'therapist'})
        Staff.create({'team_id': cls.team_3.id, 'partner_id': cls.tp_head.partner_id.id, 'role': 'head_therapist'})
        cls.multi = env['sports.patient'].create({
            'first_name': 'Multi', 'last_name': 'Synthetic',
            'team_ids': [Command.set([cls.team_1.id, cls.team_2.id])]})
        cls.lonely = env['sports.patient'].create({
            'first_name': 'Lonely', 'last_name': 'Synthetic',
            'team_ids': [Command.set([cls.team_1.id])]})
        cls.headed = env['sports.patient'].create({
            'first_name': 'Headed', 'last_name': 'Synthetic',
            'team_ids': [Command.set([cls.team_3.id])]})

    def _unverified(self, player, diagnosis):
        injury = self.env['sports.patient.injury'].create({'patient_id': player.id, 'diagnosis': diagnosis})
        injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
        return injury

    def _todos(self, injury):
        return self.env['mail.activity'].search(injury._verify_activity_domain())


@tagged('post_install', '-at_install')
class TestTodoRouting1664(Routing1664Common):

    # -- AC-1 -------------------------------------------------------------
    def test_multi_team_first_team_without_therapist(self):
        injury = self._unverified(self.multi, 'Synthetic knee')
        self.env['sports.patient.injury']._cron_create_injury_verification_tasks()
        self.env['sports.patient.injury']._cron_create_injury_verification_tasks()
        todos = self._todos(injury)
        self.assertEqual(len(todos), 1, 'one To-Do only')
        self.assertEqual(todos.user_id, self.tp_second)

    def test_no_therapist_anywhere_goes_to_clinic_admin(self):
        injury = self._unverified(self.lonely, 'Synthetic wrist')
        self.env['sports.patient.injury']._cron_create_injury_verification_tasks()
        todos = self._todos(injury)
        self.assertEqual(len(todos), 1)
        self.assertTrue(todos.user_id.has_group('bemade_sports_clinic.group_sports_clinic_admin'))
        self.assertEqual(todos.user_id, self.env['sports.patient']._sc_first_clinic_admin())

    def test_head_therapist_preferred(self):
        injury = self._unverified(self.headed, 'Synthetic hip')
        self.env['sports.patient.injury']._cron_create_injury_verification_tasks()
        self.assertEqual(self._todos(injury).user_id, self.tp_head)

    def test_reporter_team_first(self):
        # The player is on team 2 (therapist « second ») and team 3 (head
        # therapist « head »); a therapist of team 3 reports → team 3 first.
        self.multi.team_ids = [Command.set([self.team_2.id, self.team_3.id])]
        injury = self.env['sports.patient.injury'].with_user(self.tp_head).sudo().create({
            'patient_id': self.multi.id, 'diagnosis': 'Synthetic ankle'})
        injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
        self.assertEqual(self.multi._sc_todo_route(
            self.env['sports.patient']._sc_user_teams(self.tp_head)), self.tp_head)
        self.assertEqual(self.multi._sc_todo_route(), self.tp_second, 'by team id without a reporter')

    def test_incomplete_file_todo_uses_the_same_routing(self):
        # A coach (no therapist rights) created the player: routed like the
        # verification To-Do (team 1 has no therapist → team 2's therapist).
        player = self.env['sports.patient'].with_user(self.coach2).sudo().create({
            'first_name': 'Coachmade', 'last_name': 'Synthetic',
            'team_ids': [Command.set([self.team_1.id, self.team_2.id])]})
        player.sudo().create_uid = self.coach2
        self.assertEqual(player._sc_incomplete_todo_assignee(), self.tp_second)

    # -- AC-2 -------------------------------------------------------------
    def test_notepad_reminder_in_my_activities(self):
        note = self.env['sports.quick.note'].with_user(self.tp).create({'note': 'Synthetic reminder'})
        self.env.cr.execute("UPDATE sports_quick_note SET create_date = %s WHERE id = %s",
                            (fields.Datetime.now() - timedelta(days=400), note.id))
        self.env.invalidate_all()
        self.env['sports.quick.note']._cron_escalate_stale_notes()
        reminder = self.env['mail.activity'].search([
            ('res_model', '=', 'sports.quick.note'), ('res_id', '=', note.id), ('user_id', '=', self.tp.id)])
        self.assertEqual(len(reminder), 1)
        reminder.date_deadline = fields.Date.today() - timedelta(days=1)
        self._switch(True)
        self._login_tp()
        resp = self.url_open('/my/activities')
        tree = lxml_html.fromstring(resp.text)
        row = tree.xpath('//*[@data-sc-activity-row="%s"]' % reminder.id)
        self.assertTrue(row, 'the notepad reminder is listed')
        self.assertTrue(row[0].xpath('.//a[@href="/my/notepad#note-%s"]' % note.id))
        self.assertNotIn('Synthetic reminder', resp.text, 'never the note text in the list')
        count = self.url_open('/my/activities/overdue/count').json()['count']
        self.assertGreaterEqual(count, 1)
        # Another therapist: not listed.
        self.authenticate('r1664.second@example.com', 'r1664.second@example.com')
        tree = lxml_html.fromstring(self.url_open('/my/activities').text)
        self.assertFalse(tree.xpath('//*[@data-sc-activity-row="%s"]' % reminder.id))
        # The owner opens it.
        self._login_tp()
        self.assertEqual(self.url_open('/my/activity/%s' % reminder.id).status_code, 200)

    # -- AC-3 -------------------------------------------------------------
    def test_reassign_everywhere(self):
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self.url_open('/my/activities').text)
        self.assertTrue(tree.xpath('//button[@data-sc-action="activity.reassign"]'))
        self.assertTrue(tree.xpath('//dialog[@id="sc_activity_reassign_sheet"]'))
        tree = lxml_html.fromstring(self.url_open(
            '/my/player?player_id=%s&tab=activities' % self.player.id).text)
        panel = tree.xpath('//section[@data-sc-tab-panel="activities"]')[0]
        self.assertTrue(panel.xpath('.//button[@data-sc-action="activity.reassign"]'))
        self.assertTrue(panel.xpath('.//dialog[@id="sc_activity_reassign_sheet"]//option[@value]'))
        tree = lxml_html.fromstring(self.url_open('/my/activity/%s' % self.act_player.id).text)
        self.assertTrue(tree.xpath('//div[contains(@class, "o_sc_actionbar")]//button[@data-sc-action="activity.reassign"]'))
        self.assertTrue(tree.xpath('//dialog[@id="sc_activity_reassign_sheet"]//option[@value="%s"]' % self.tp.id))

    # -- AC-4 -------------------------------------------------------------
    def test_coach_two_teams_request_removal(self):
        self._switch(True)
        self.authenticate('r1664.coach@example.com', 'r1664.coach@example.com')
        tree = lxml_html.fromstring(self.url_open('/my/player?player_id=%s' % self.multi.id).text)
        self.assertTrue(tree.xpath('//button[@data-sc-action="player.request_removal"]'))
        sheet = tree.xpath('//dialog[@id="sc_request_removal_sheet"]')[0]
        form = sheet.xpath('.//form')[0]
        self.assertEqual(form.get('action'), '/my/player/%s/request_removal' % self.multi.id)
        options = sorted(int(v) for v in sheet.xpath('.//select[@name="team_id"]/option/@value') if v)
        self.assertEqual(options, sorted([self.team_1.id, self.team_2.id]))
        csrf = form.xpath('.//input[@name="csrf_token"]/@value')[0]
        self.url_open('/my/player/%s/request_removal' % self.multi.id,
                      data={'csrf_token': csrf, 'reason': 'Synthetic reason'}, allow_redirects=False)
        self.multi.invalidate_recordset()
        self.assertFalse(self.multi.pending_removal, 'no team, no request')
        self.url_open('/my/player/%s/request_removal' % self.multi.id,
                      data={'csrf_token': csrf, 'reason': 'Synthetic reason', 'team_id': self.team_2.id},
                      allow_redirects=False)
        self.multi.invalidate_recordset()
        self.assertTrue(self.multi.pending_removal)
        # A single shared team keeps the per-team action (no select).
        tree = lxml_html.fromstring(self.url_open('/my/player?player_id=%s' % self.lonely.id).text)
        sheet = tree.xpath('//dialog[@id="sc_request_removal_sheet"]')[0]
        self.assertFalse(sheet.xpath('.//select[@name="team_id"]'))
        self.assertEqual(sheet.xpath('.//form/@action'),
                         ['/my/team/%s/player/%s/request_removal' % (self.team_1.id, self.lonely.id)])
