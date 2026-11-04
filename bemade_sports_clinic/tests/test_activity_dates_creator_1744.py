"""Task 1744 — activities: no NEW due date in the past (portal routes), and
« Créé automatiquement » for what the system created. Synthetic fixtures
only (this repository is public).

Acceptance criteria:

* UC-1 Each portal route refuses a due date before the user's today
  (Québec), with « The due date cannot be in the past. » (« La date
  d'échéance ne peut pas être dans le passé. »): the create (/my/activity/save
  → ?error=past_deadline), the in-place save (/my/app/save/mail.activity →
  400 + message), the legacy update and reschedule. Today and later pass.
* UC-2 An overdue activity saved WITHOUT changing its date is fine (the
  stored date is not « new »); crons / internal code are not blocked.
* UC-3 The date inputs carry ``min`` = today (the stored overdue date on the
  edit form).
* UC-4 « Created by »: « Created automatically » (« Créé automatiquement »)
  when the creator is OdooBot / the superuser or the public user; a person
  keeps their name.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

MSG = 'The due date cannot be in the past.'
MSG_FR = "La date d'échéance ne peut pas être dans le passé."


@tagged('post_install', '-at_install')
class TestActivityDates1744(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)
        self.today = fields.Date.context_today(self.tp)
        self.yesterday = self.today - timedelta(days=1)

    def _post(self, url, **data):
        data['csrf_token'] = self._csrf()
        return self.url_open(url, data=data, allow_redirects=False)

    def _new(self, summary, day):
        return self._post('/my/activity/save', model='sports.patient', res_id=self.player.id,
                          summary=summary, user_id=self.tp.id, date_deadline=day.isoformat())

    def _found(self, summary):
        return self.env['mail.activity'].search([('summary', '=', summary)])

    # -- UC-1 ---------------------------------------------------------------
    def test_create(self):
        self._login_tp()
        resp = self._new('SC1744 past', self.yesterday)
        self.assertIn('error=past_deadline', resp.headers['Location'])
        self.assertFalse(self._found('SC1744 past'))
        _text, tree = self._get(resp.headers['Location'])
        self.assertIn(MSG, ' '.join(tree.xpath('//*[@data-sc-flash-error]//text()')))
        self._new('SC1744 today', self.today)
        self.assertTrue(self._found('SC1744 today'))

    def test_inline_save(self):
        self._login_tp()
        act = self.act_player
        act.date_deadline = self.today + timedelta(days=3)
        url = '/my/app/save/mail.activity/%s' % act.id

        def save(day):
            act.invalidate_recordset()
            return self._post(url, field='date_deadline', value=day.isoformat(),
                              write_date=fields.Datetime.to_string(act.sudo().write_date))
        resp = save(self.yesterday)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['message'], MSG)
        self.assertEqual(act.date_deadline, self.today + timedelta(days=3))
        self.assertEqual(save(self.today).status_code, 200)
        self.assertEqual(act.date_deadline, self.today)

    def test_legacy_update_and_reschedule(self):
        self._login_tp()
        act = self.act_player
        act.date_deadline = self.today + timedelta(days=3)
        resp = self._post('/my/activity/update', activity_id=act.id, summary='Player task',
                          date_deadline=self.yesterday.isoformat())
        self.assertIn('error=past_deadline', resp.headers['Location'])
        self.assertEqual(act.date_deadline, self.today + timedelta(days=3))
        resp = self._post('/my/activity/reschedule', activity_id=act.id,
                          new_deadline=self.yesterday.isoformat(), return_url='/my/activities')
        self.assertIn('error=past_deadline', resp.headers['Location'])
        act.invalidate_recordset()
        self.assertEqual(act.date_deadline, self.today + timedelta(days=3))
        # A malformed date: refused, not stored (was written as is).
        resp = self._post('/my/activity/reschedule', activity_id=act.id, new_deadline='2026-13-45',
                          return_url='/my/activities')
        self.assertIn('error=', resp.headers['Location'])
        tomorrow = self.today + timedelta(days=1)
        self._post('/my/activity/reschedule', activity_id=act.id, new_deadline=tomorrow.isoformat(),
                   return_url='/my/activities')
        act.invalidate_recordset()
        self.assertEqual(act.date_deadline, tomorrow)

    # -- UC-2 ---------------------------------------------------------------
    def test_overdue_kept_and_internal_free(self):
        self._login_tp()
        act = self.act_player
        old = self.today - timedelta(days=5)
        act.date_deadline = old  # internal code: never blocked
        resp = self._post('/my/activity/update', activity_id=act.id, summary='Renamed 1744',
                          date_deadline=old.isoformat())
        self.assertNotIn('error=', resp.headers['Location'])
        act.invalidate_recordset()
        self.assertEqual((act.summary, act.date_deadline), ('Renamed 1744', old))

    # -- UC-3 ---------------------------------------------------------------
    def test_min_on_inputs(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        self.assertEqual(tree.xpath('//input[@id="sc_add_activity_deadline"]/@min'), [self.today.isoformat()])
        _text, tree = self._get('/my/activity/create?model=sports.patient&res_id=%s' % self.player.id)
        self.assertEqual(tree.xpath('//input[@id="sc_act_deadline"]/@min'), [self.today.isoformat()])

    # -- UC-1 / UC-4 French ------------------------------------------------------
    def test_french(self):
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        self.tp.write({'lang': 'fr_CA'})
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self._new('SC1744 past fr', self.yesterday)
        _text, tree = self._get(resp.headers['Location'])
        self.assertIn(MSG_FR, ' '.join(tree.xpath('//*[@data-sc-flash-error]//text()')))
        self.assertEqual(self.act_player.with_context(lang='fr_CA').sc_created_by_label, 'Créé automatiquement')


@tagged('post_install', '-at_install')
class TestActivityCreator1744(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _creator(self, activity):
        _text, tree = self._get('/my/activity/%s' % activity.id)
        return ' '.join(tree.xpath('//*[@data-sc-activity-creator]//text()')).strip()

    def test_creator_label(self):
        self._login_tp()
        # Fixtures are created by the superuser (OdooBot): « automatically ».
        self.assertEqual(self.act_player.create_uid.id, 1)
        self.assertEqual(self._creator(self.act_player), 'Created automatically')
        public = self.env.ref('base.public_user')
        act_public = self.env['mail.activity'].with_user(public).sudo(False).with_context(
            active_test=False).sudo().create({
                'res_model_id': self.env['ir.model']._get_id('sports.patient'),
                'res_id': self.player.id, 'summary': 'SC1744 public', 'user_id': self.tp.id})
        act_public.sudo().write({'create_uid': public.id})
        self.assertEqual(self._creator(act_public), 'Created automatically')
        # A person keeps their name (created from the portal).
        self.url_open('/my/activity/save', data={
            'csrf_token': self._csrf(), 'model': 'sports.patient', 'res_id': self.player.id,
            'summary': 'SC1744 by a person', 'user_id': self.tp.id,
            'date_deadline': fields.Date.context_today(self.tp).isoformat()})
        mine = self.env['mail.activity'].search([('summary', '=', 'SC1744 by a person')])
        self.assertEqual(mine.create_uid, self.tp)
        self.assertEqual(self._creator(mine), self.tp.name)
        # The popout shows the same.
        _text, tree = self._get('/my/activity/%s/popout' % self.act_player.id)
        self.assertIn('Created automatically', ' '.join(tree.xpath('//*[@data-sc-activity-creator]//text()')))
