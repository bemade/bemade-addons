"""Task 1539 — activities on the app shell. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-A1 (AC1) Switch OFF: /my/activities, the create / edit / detail pages
  and the /my/team/activities wrapper render today's templates.
* UC-A2 (AC2) /my/activities in the shell: segmented tabs (all / overdue /
  today / planned) with counts; activity rows with their due-date chip;
  the complete / reschedule / cancel sheets post to today's routes with a
  CSRF token and a same-site return URL; no « Réaffecter » on the
  self-scoped list, as today.
* UC-A3 (AC2) Context views (/my/team/activities): the reassign sheet lists
  the requester's assignable users (#1500) and posts to today's route;
  « Ajouter une activité » links to the create page with an encoded
  return URL.
* UC-A4 (AC2) Create / edit / detail in the shell post to today's routes;
  the assignee select carries the advisory no-access ids (#1402).
* UC-A5 (AC2) The team page's Activities tab uses the shell list (no legacy
  partial) and its add sheet creates an activity through today's route.
"""
from datetime import timedelta
from urllib.parse import quote

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellActivities1539(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        today = fields.Date.today()
        cls.act_player.date_deadline = today - timedelta(days=2)
        cls.act_team.date_deadline = today
        cls.act_event.date_deadline = today + timedelta(days=5)

    # -- UC-A1 -----------------------------------------------------------
    def test_switch_off_legacy(self):
        self._login_tp()
        for url, marker in (
                ('/my/activities', 'id="all-tab"'),
                ('/my/activity/create?model=sports.patient&res_id=%s' % self.player.id,
                 'action="/my/activity/save"'),
                ('/my/activity/%s' % self.act_player.id, 'action="/my/activity/complete"'),
                ('/my/activity/%s/edit' % self.act_player.id, 'action="/my/activity/update"'),
                ('/my/team/activities?team_id=%s' % self.team_a.id, 'id="reassignModal"'),
                ('/my/event/activities?event_id=%s' % self.event.id, 'id="reassignModal"')):
            text, tree = self._get(url)
            self.assertIn(marker, text, url)
            self.assertIsNone(self._shell(tree), url)

    # -- UC-A2 -----------------------------------------------------------
    def test_my_activities_in_shell(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._get('/my/activities')
        self.assertIsNotNone(self._shell(tree))
        self.assertEqual(tree.xpath('//nav[@data-sc-tabs]/a/@data-sc-tab'),
                         ['all', 'overdue', 'today', 'planned'])
        overdue = tree.xpath('//section[@data-sc-tab-panel="overdue"]//*[@data-sc-activity-row]'
                             '/@data-sc-activity-row')
        self.assertEqual(overdue, [str(self.act_player.id)])
        states = tree.xpath('//section[@data-sc-tab-panel="all"]//*[@data-sc-activity-row="%s"]'
                            '/@data-sc-activity-state' % self.act_team.id)
        self.assertEqual(states, ['today'])
        for sheet in ('complete', 'reschedule', 'cancel'):
            form = tree.xpath('//dialog[@id="sc_activity_%s_sheet"]//form' % sheet)[0]
            self.assertEqual(form.get('action'), '/my/activity/%s' % sheet)
            self.assertTrue(form.xpath('.//input[@name="csrf_token"]/@value')[0])
            self.assertEqual(form.xpath('.//input[@name="return_url"]/@value'), ['/my/activities'])
        self.assertFalse(tree.xpath('//dialog[@id="sc_activity_reassign_sheet"]'))
        # ?tab= deep link.
        _text, tree = self._get('/my/activities?tab=planned')
        self.assertIsNone(tree.xpath('//section[@data-sc-tab-panel="planned"]')[0].get('hidden'))

    def test_cancel_from_sheet_returns(self):
        self._switch(True)
        self._login_tp()
        resp = self.url_open('/my/activity/cancel', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_team.id,
            'return_url': '/my/activities?tab=today'}, allow_redirects=False)
        self.assertIn('/my/activities?tab=today&success=activity_cancelled',
                      resp.headers['Location'])
        self.assertFalse(self.act_team.exists())

    # -- UC-A3 -----------------------------------------------------------
    def test_team_context_view_reassign(self):
        self._switch(True)
        self._login_tp()
        url = '/my/team/activities?team_id=%s' % self.team_a.id
        _text, tree = self._get(url)
        self.assertIsNotNone(self._shell(tree))
        form = tree.xpath('//dialog[@id="sc_activity_reassign_sheet"]//form')[0]
        self.assertEqual(form.get('action'), '/my/activity/reassign')
        options = form.xpath('.//select[@name="new_user_id"]/option/@value')
        self.assertIn(str(self.coach.id), options)
        add = tree.xpath('//header//a[@data-sc-action="activity.add"]/@href')
        self.assertEqual(add, ['/my/activity/create?model=sports.team&res_id=%s&return_url=%s'
                               % (self.team_a.id, quote(url, safe=''))])
        resp = self.url_open('/my/activity/reassign', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_team.id,
            'new_user_id': self.coach.id, 'return_url': url}, allow_redirects=False)
        self.assertIn('success=activity_reassigned', resp.headers['Location'])
        self.assertEqual(self.act_team.user_id, self.coach)

    # -- UC-A4 -----------------------------------------------------------
    def test_create_edit_detail_in_shell(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/activity/create?model=sports.patient&res_id=%s' % self.player.id)
        form = tree.xpath('//form[@data-sc-form="activity.form"]')[0]
        self.assertEqual(form.get('action'), '/my/activity/save')
        select = form.xpath('.//select[@name="user_id"]')[0]
        self.assertEqual(select.get('data-sc-assignee-select'), '1')
        self.assertIsNotNone(select.get('data-sc-no-access'))
        _text, tree = self._get('/my/activity/%s/edit' % self.act_player.id)
        form = tree.xpath('//form[@data-sc-form="activity.form"]')[0]
        self.assertEqual(form.get('action'), '/my/activity/update')
        self.assertEqual(form.xpath('.//input[@name="summary"]/@value'), ['Player task'])
        _text, tree = self._get('/my/activity/%s' % self.act_player.id)
        self.assertTrue(tree.xpath('//*[@data-sc-section="activity.detail"]'))
        form = tree.xpath('//dialog[@id="sc_activity_complete_sheet"]//form')[0]
        self.assertEqual(form.xpath('.//input[@name="return_url"]/@value'),
                         ['/my/player?player_id=%s' % self.player.id])

    # -- UC-A5 -----------------------------------------------------------
    def test_team_page_tab_uses_shell_list(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/team?team_id=%s&tab=activities' % self.team_a.id)
        panel = tree.xpath('//section[@data-sc-tab-panel="activities"]')[0]
        self.assertFalse(panel.xpath('.//*[contains(@class, "o_sc_legacy")]'))
        self.assertTrue(panel.xpath('.//*[@data-sc-activity-row="%s"]' % self.act_team.id))
        form = panel.xpath('.//details[@data-sc-section="activity.add"]//form')[0]
        self.assertEqual(form.get('action'), '/my/activity/save')
        count = self.env['mail.activity'].search_count([('res_model', '=', 'sports.team')])
        resp = self.url_open('/my/activity/save', data={
            'csrf_token': self._csrf(), 'model': 'sports.team', 'res_id': self.team_a.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Coach synthetic task', 'user_id': self.coach.id,
            'date_deadline': fields.Date.to_string(fields.Date.today()),
            'return_url': '/my/team?team_id=%s&tab=activities' % self.team_a.id,
        }, allow_redirects=False)
        self.assertIn('tab=activities', resp.headers['Location'])
        self.assertEqual(self.env['mail.activity'].search_count(
            [('res_model', '=', 'sports.team')]), count + 1)
