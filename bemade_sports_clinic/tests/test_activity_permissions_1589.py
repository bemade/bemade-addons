"""Task 1589 — activity permissions: who sees, edits, completes and cancels.
Synthetic fixtures only (invented names and summaries).

Owner decision 2026-10-12:

* Therapists (team TPs) and the assignee act (modify / complete / cancel /
  reschedule / reassign) on the activities of their team scope.
* Coaches see and act ONLY on the activities assigned to them or created by
  them — they never see any other activity (no list row, no count, no
  detail page, no download).
* Clinic administrators (and system admins) are unchanged: everything.

Acceptance criteria:

* UC-P1 (role x action matrix) view list, view detail, complete, cancel,
  reschedule, reassign, pencil save:
  coach-assignee OK, coach-creator OK, coach on another's activity refused
  (not even listed), TP in scope OK, TP out of scope refused, clinic admin OK.
* UC-P2 The coach record rule hides every other activity, including from
  ORM searches / counts made as the coach (the lists, tabs and the home
  counter search as the user).
* UC-P3 Coach writes run with sudo() only after the helper check; a refused
  act redirects with ``error=not_allowed`` and changes nothing.
* UC-P4 An activity a coach creates from the portal (sudo create) has the
  coach as ``create_uid`` — so the coach keeps seeing it once it is
  assigned to someone else.
* UC-P5 App shell: the detail page's Cancel / Reschedule / Done bar and the
  list rows' actions are shown only to who may act; the refusal flash reads
  « Vous ne pouvez pas modifier cette activité. » in fr_CA.
* UC-P6 The noupdate-safe migration (migrations/19.0.1.59.0) carries the
  same domain as the XML rule and rewrites an old rule.
* UC-P7 The daily digest's « verifications pending » count of a coach line
  counts only the coach's own activities.
* UC-P8 (browser tour) a coach completes their own activity from the
  player's Activities tab and never sees the therapist's.
"""
import importlib.util
import os
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.controllers.access_control_mixin import AccessControlMixin
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon



def _load_migration():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'migrations', '19.0.1.59.0', 'post-migrate.py')
    spec = importlib.util.spec_from_file_location('bsc_migration_19_0_1_59_0', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


class ActivityPermissionsCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        admin_g = env.ref('bemade_sports_clinic.group_sports_clinic_admin').id
        new_user = env['res.users'].with_context(no_reset_password=True).create
        # A therapist of ANOTHER team (out of scope for team A's activities).
        cls.tp_b = new_user({
            'name': 'PP TP B', 'login': 'pp.tpb@example.com', 'password': 'pp-tpb',
            'group_ids': [Command.set([portal, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_b.id, 'partner_id': cls.tp_b.partner_id.id, 'role': 'therapist',
        })
        # A clinic administrator staffing no team.
        cls.clinic_admin = new_user({
            'name': 'PP Clinic Admin', 'login': 'pp.admin@example.com', 'password': 'pp-admin',
            'group_ids': [Command.set([admin_g])],
        })
        todo = env.ref('mail.mail_activity_data_todo')
        patient_model = env['ir.model']._get('sports.patient').id

        def vals(summary, user, res_id=None):
            return {
                'res_model_id': patient_model, 'res_id': res_id or cls.player.id,
                'activity_type_id': todo.id, 'summary': summary, 'user_id': user.id,
            }
        Activity = env['mail.activity']
        # Assigned to the coach (created by someone else).
        cls.act_coach_assigned = Activity.create(vals('Coach assigned task', cls.coach))
        # Created by the coach the way the portal does it (sudo keeps the
        # uid), assigned to the therapist.
        cls.act_coach_created = Activity.with_user(cls.coach).sudo().create(
            vals('Coach created task', cls.tp))
        # Assigned to the coach but on another team's player: out of scope.
        cls.act_coach_out_of_scope = Activity.create(
            vals('Coach other team task', cls.coach, res_id=cls.player_b.id))
        # cls.act_player / act_injury / act_team / act_event: the TP's,
        # created by the superuser — a coach never sees them.
        cls.coach_own = cls.act_coach_assigned | cls.act_coach_created
        cls.tp_only = cls.act_player | cls.act_injury | cls.act_team | cls.act_event

    # -- helpers ---------------------------------------------------------
    def _login(self, who):
        logins = {
            'coach': ('pc.coach@example.com', 'pc-coach'),
            'tp': ('pc.tp@example.com', 'pc-tp'),
            'tp_b': ('pp.tpb@example.com', 'pp-tpb'),
            'admin': ('pp.admin@example.com', 'pp-admin'),
        }
        self.authenticate(*logins[who])

    def _post(self, url, **data):
        data['csrf_token'] = self._csrf()
        return self.url_open(url, data=data, allow_redirects=False)

    def _save(self, record, field, value):
        record.invalidate_recordset()
        return self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data={
            'field': field, 'value': value, 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(record.write_date)}, allow_redirects=False)

    @staticmethod
    def _open(activity):
        """Still open: neither deleted (cancel) nor archived (done)."""
        activity.invalidate_recordset()
        return bool(activity.exists() and activity.active)

    def _detail_status(self, activity):
        return self.url_open('/my/activity/%s' % activity.id, allow_redirects=False).status_code

    @staticmethod
    def _row_ids(tree):
        return {int(i) for i in tree.xpath('//*[@data-sc-activity-row]/@data-sc-activity-row')}


@tagged('post_install', '-at_install')
class TestActivityPermissions1589(ActivityPermissionsCommon):

    # -- UC-P2 -----------------------------------------------------------
    def test_coach_rule_hides_others(self):
        Activity = self.env['mail.activity'].with_user(self.coach)
        domain = [('res_model', 'in', ('sports.patient', 'sports.team', 'sports.event'))]
        self.assertEqual(Activity.search(domain), self.coach_own)
        self.assertEqual(Activity.search_count(domain), 2)
        # The therapist still sees the whole team-A scope.
        tp_seen = self.env['mail.activity'].with_user(self.tp).search(domain)
        self.assertEqual(tp_seen, self.coach_own | self.tp_only)
        # The counters on the player / team / event follow the rule.
        self.assertEqual(self.player.with_user(self.coach).activity_count, 2)
        self.assertEqual(self.team_a.with_user(self.coach).activity_count, 0)

    def test_coach_lists_only_own(self):
        self._switch(True)
        self._login('coach')
        for url in ('/my/activities?model=sports.patient&res_id=%s' % self.player.id,
                    '/my/player?player_id=%s&tab=activities' % self.player.id):
            _text, tree = self._get(url)
            self.assertEqual(self._row_ids(tree), set(self.coach_own.ids), url)
        _text, tree = self._get('/my/team?team_id=%s&tab=activities' % self.team_a.id)
        self.assertNotIn(self.act_team.id, self._row_ids(tree))
        # « My activities »: the ones assigned to the coach in scope.
        _text, tree = self._get('/my/activities')
        self.assertEqual(self._row_ids(tree), {self.act_coach_assigned.id})

    def test_coach_legacy_list_only_own(self):
        self._login('coach')
        text, _tree = self._get('/my/activities?model=sports.patient&res_id=%s' % self.player.id)
        self.assertIn('Coach assigned task', text)
        self.assertIn('Coach created task', text)
        self.assertNotIn('Player task', text)
        self.assertNotIn('Injury task', text)

    def test_tp_lists_scope(self):
        self._switch(True)
        self._login('tp')
        _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        self.assertEqual(self._row_ids(tree),
                         set((self.coach_own | self.act_player | self.act_injury).ids))

    # -- UC-P1: detail -----------------------------------------------------
    @mute_logger('odoo.http', 'odoo.addons.base.models.ir_rule')
    def test_detail_matrix(self):
        self._switch(True)
        cases = [
            ('coach', self.act_coach_assigned, 200),
            ('coach', self.act_coach_created, 200),
            ('coach', self.act_player, 404),
            ('coach', self.act_team, 404),
            ('coach', self.act_event, 404),
            ('coach', self.act_coach_out_of_scope, 404),
            ('tp', self.act_player, 200),
            ('tp', self.act_coach_assigned, 200),
            # Task 1589: team / event activities of the scope open for a TP
            # (the #1586 view rule only knew patients).
            ('tp', self.act_team, 200),
            ('tp', self.act_event, 200),
            ('tp_b', self.act_player, 404),
            ('tp_b', self.act_team, 404),
            ('admin', self.act_player, 200),
            ('admin', self.act_team, 200),
            ('admin', self.act_coach_out_of_scope, 200),
        ]
        for who, activity, expected in cases:
            self._login(who)
            with self.subTest(who=who, activity=activity.summary):
                self.assertEqual(self._detail_status(activity), expected)

    @mute_logger('odoo.http')
    def test_coach_legacy_edit_page(self):
        self._login('coach')
        self.assertEqual(self.url_open('/my/activity/%s/edit' % self.act_coach_created.id).status_code, 200)
        self.assertEqual(self.url_open('/my/activity/%s/edit' % self.act_player.id).status_code, 404)

    # -- UC-P1 / UC-P3: complete ------------------------------------------
    def _complete(self, activity, **extra):
        return self._post('/my/activity/complete', activity_id=activity.id,
                          feedback='Synthetic feedback', **extra)

    def test_coach_completes_own(self):
        self._login('coach')
        for activity in self.coach_own:
            resp = self._complete(activity, return_url='/my/activities')
            self.assertIn(resp.status_code, (302, 303))
            self.assertIn('success=activity_done', resp.headers['Location'])
            self.assertFalse(self._open(activity))
        # The done message is authored by the coach (sudo keeps the uid).
        message = self.env['mail.message'].search([
            ('model', '=', 'sports.patient'), ('res_id', '=', self.player.id),
            ('mail_activity_type_id', '!=', False)], order='id desc', limit=1)
        self.assertEqual(message.author_id, self.coach.partner_id)

    def test_complete_refused(self):
        for who, activity in (('coach', self.act_player), ('coach', self.act_coach_out_of_scope),
                              ('tp_b', self.act_player)):
            self._login(who)
            resp = self._complete(activity, return_url='/my/activities')
            self.assertIn(resp.status_code, (302, 303))
            self.assertIn('error=not_allowed', resp.headers['Location'])
            self.assertTrue(self._open(activity), who)

    def test_complete_allowed_tp_and_admin(self):
        self._login('tp')
        self._complete(self.act_coach_assigned)
        self.assertFalse(self._open(self.act_coach_assigned))
        self._login('admin')
        self._complete(self.act_coach_out_of_scope)
        self.assertFalse(self._open(self.act_coach_out_of_scope))

    # -- UC-P1 / UC-P3: cancel --------------------------------------------
    def test_cancel_matrix(self):
        refused = [('coach', self.act_player), ('coach', self.act_team),
                   ('tp_b', self.act_coach_assigned)]
        for who, activity in refused:
            self._login(who)
            resp = self._post('/my/activity/cancel', activity_id=activity.id)
            self.assertIn('error=not_allowed', resp.headers['Location'])
            self.assertTrue(self._open(activity), who)
        allowed = [('coach', self.act_coach_assigned), ('coach', self.act_coach_created),
                   ('tp', self.act_team), ('admin', self.act_event)]
        for who, activity in allowed:
            self._login(who)
            resp = self._post('/my/activity/cancel', activity_id=activity.id,
                              return_url='/my/activities')
            self.assertIn('success=activity_cancelled', resp.headers['Location'])
            self.assertFalse(activity.exists(), who)

    # -- UC-P1: reschedule ------------------------------------------------
    def test_reschedule_matrix(self):
        new_day = '2031-03-04'
        self._login('coach')
        # The creator (not the assignee) may reschedule now.
        resp = self._post('/my/activity/reschedule', activity_id=self.act_coach_created.id,
                          new_deadline=new_day, return_url='/my/activities')
        self.assertIn('success=activity_updated', resp.headers['Location'])
        self.assertEqual(fields.Date.to_string(self.act_coach_created.date_deadline), new_day)
        before = self.act_player.date_deadline
        resp = self._post('/my/activity/reschedule', activity_id=self.act_player.id,
                          new_deadline=new_day)
        self.assertIn('error=not_allowed', resp.headers['Location'])
        self.act_player.invalidate_recordset()
        self.assertEqual(self.act_player.date_deadline, before)
        # A TP in scope reschedules an activity assigned to someone else.
        self._login('tp')
        self._post('/my/activity/reschedule', activity_id=self.act_coach_assigned.id,
                   new_deadline=new_day)
        self.assertEqual(fields.Date.to_string(self.act_coach_assigned.date_deadline), new_day)

    # -- UC-P1: reassign --------------------------------------------------
    def test_reassign_matrix(self):
        self._login('coach')
        resp = self._post('/my/activity/reassign', activity_id=self.act_coach_assigned.id,
                          new_user_id=self.tp.id, return_url='/my/activities')
        self.assertIn('success=activity_reassigned', resp.headers['Location'])
        self.assertEqual(self.act_coach_assigned.user_id, self.tp)
        resp = self._post('/my/activity/reassign', activity_id=self.act_player.id,
                          new_user_id=self.coach.id)
        self.assertIn('error=not_allowed', resp.headers['Location'])
        self.assertEqual(self.act_player.user_id, self.tp)
        self._login('tp_b')
        self._post('/my/activity/reassign', activity_id=self.act_player.id,
                   new_user_id=self.tp_b.id)
        self.assertEqual(self.act_player.user_id, self.tp)
        self._login('tp')
        self._post('/my/activity/reassign', activity_id=self.act_coach_created.id,
                   new_user_id=self.coach.id)
        self.assertEqual(self.act_coach_created.user_id, self.coach)

    def test_update_route(self):
        self._login('coach')
        self._post('/my/activity/update', activity_id=self.act_coach_created.id,
                   summary='Coach renamed')
        self.assertEqual(self.act_coach_created.summary, 'Coach renamed')
        resp = self._post('/my/activity/update', activity_id=self.act_player.id,
                          summary='Nope')
        self.assertIn('error=not_allowed', resp.headers['Location'])
        self.assertEqual(self.act_player.summary, 'Player task')

    # -- UC-P1: pencil save -----------------------------------------------
    def test_pencil_matrix(self):
        self._switch(True)
        self._login('coach')
        self.assertEqual(self._save(self.act_coach_assigned, 'summary', 'Coach pencil').status_code, 200)
        self.assertEqual(self.act_coach_assigned.summary, 'Coach pencil')
        self.assertEqual(self._save(self.act_coach_created, 'note', 'Synthetic coach note').status_code, 200)
        with mute_logger('odoo.http'):
            self.assertIn(self._save(self.act_player, 'summary', 'Nope').status_code, (403, 404))
            self._login('tp_b')
            self.assertIn(self._save(self.act_player, 'summary', 'Nope').status_code, (403, 404))
        self.assertEqual(self.act_player.summary, 'Player task')
        self._login('tp')
        self.assertEqual(self._save(self.act_coach_assigned, 'summary', 'TP pencil').status_code, 200)
        self._login('admin')
        self.assertEqual(self._save(self.act_team, 'summary', 'Admin pencil').status_code, 200)

    # -- UC-P4 -----------------------------------------------------------
    def test_portal_created_activity_keeps_coach_uid(self):
        self._login('coach')
        resp = self._post('/my/activity/save', model='sports.patient', res_id=self.player.id,
                          activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                          summary='Coach portal created', user_id=self.tp.id,
                          date_deadline='2031-01-02', return_url='/my/activities')
        self.assertIn('success=activity_created', resp.headers['Location'])
        created = self.env['mail.activity'].search([('summary', '=', 'Coach portal created')])
        self.assertEqual(len(created), 1)
        self.assertEqual(created.create_uid, self.coach)
        self.assertEqual(created.user_id, self.tp)
        # Assigned to the therapist, still the coach's: visible and actionable.
        self.assertEqual(self._detail_status(created), 200)
        self.assertIn(created, self.env['mail.activity'].with_user(self.coach).search([]))

    # -- UC-P5 -----------------------------------------------------------
    def test_shell_buttons_follow_act_rule(self):
        self._switch(True)
        self._login('coach')
        _text, tree = self._get('/my/activity/%s' % self.act_coach_created.id)
        bar = tree.xpath('//div[contains(@class, "o_sc_actionbar")]')
        self.assertTrue(bar)
        actions = set(bar[0].xpath('.//@data-sc-action'))
        # Task 1664 (deliberate update): « Réassigner » on the detail page too.
        self.assertEqual(actions, {'activity.cancel', 'activity.reschedule', 'activity.complete',
                                   'activity.reassign'})
        self.assertTrue(tree.xpath('//*[@data-sc-edit-card="activity"]'))
        # Someone who may open but not act (forced) gets no bar / pencil / row actions.
        with patch.object(AccessControlMixin, '_activity_act_access', return_value=False), \
                patch.object(AccessControlMixin, '_activity_view_access', return_value=True):
            _text, tree = self._get('/my/activity/%s' % self.act_coach_created.id)
            self.assertFalse(tree.xpath('//div[contains(@class, "o_sc_actionbar")]'))
            self.assertFalse(tree.xpath('//*[@data-sc-edit-card="activity"]'))
            _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
            self.assertTrue(self._row_ids(tree))
            self.assertFalse(tree.xpath('//*[@data-sc-activity-row]//*[@data-sc-action]'))
        _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        self.assertTrue(tree.xpath(
            '//*[@data-sc-activity-row="%s"]//*[@data-sc-action="activity.complete"]'
            % self.act_coach_assigned.id))

    def test_refusal_flash(self):
        self._switch(True)
        self._login('coach')
        _text, tree = self._get('/my/activities?error=not_allowed')
        self.assertIn('You cannot change this activity.', ' '.join(tree.xpath('//text()')))

    def test_refusal_flash_legacy(self):
        # App shell OFF: the legacy activities page names the refusal
        # instead of showing an empty red box.
        self._switch(False)
        self._login('coach')
        text, _tree = self._get('/my/activities?error=not_allowed')
        self.assertIn('You cannot change this activity.', text)

    # -- UC-P6 -----------------------------------------------------------
    def test_migration_domain_matches_xml_and_rewrites(self):
        rule = self.env.ref(migration.RULE_XMLID)
        self.assertEqual(migration._normalized(rule.domain_force),
                         migration._normalized(migration.COACH_DOMAIN))
        old = "[('res_model', '=', 'sports.team')]"
        rule.write({'domain_force': old, 'perm_write': True})
        migration.migrate(self.env.cr, '19.0.1.58.0')
        rule.invalidate_recordset()
        self.assertEqual(migration._normalized(rule.domain_force),
                         migration._normalized(migration.COACH_DOMAIN))
        self.assertFalse(rule.perm_write)
        self.assertTrue(rule.perm_read)

    # -- UC-P7 -----------------------------------------------------------
    def test_digest_coach_verify_count(self):
        verify = self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'res_id': self.player.id, 'injury_id': self.injury.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Verify injury (synthetic)', 'user_id': self.tp.id,
        })
        domain = self.injury._verify_activity_domain()
        total = self.env['mail.activity'].search_count(domain)
        self.assertGreaterEqual(total, 1)
        self.assertEqual(self.tp._digest_pending_verify_count(self.team_a, 'tp'), total)
        self.assertEqual(self.coach._digest_pending_verify_count(self.team_a, 'coach'), 0)
        verify.user_id = self.coach
        self.assertEqual(self.coach._digest_pending_verify_count(self.team_a, 'coach'), 1)


@tagged('post_install', '-at_install')
class TestActivityPermissions1589Fr(ActivityPermissionsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.coach.write({'lang': 'fr_CA'})

    def test_fr_refusal_flash(self):
        self._switch(True)
        self._login('coach')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self._complete_refused()
        _text, tree = self._get(resp.headers['Location'])
        self.assertIn('Vous ne pouvez pas modifier cette activité.', ' '.join(tree.xpath('//text()')))

    def _complete_refused(self):
        return self._post('/my/activity/complete', activity_id=self.act_player.id,
                          return_url='/my/activities')


@tagged('post_install', '-at_install')
class TestActivityPermissions1589Tour(ActivityPermissionsCommon):
    """UC-P8 (static/tests/tours/sc_app_activity_permissions_tours.js)."""
    browser_size = '390x844'

    def test_coach_completes_own_tour(self):
        self._switch(True)
        self.start_tour('/my/player?player_id=%s&tab=activities' % self.player.id,
                        'sc_1589_coach_own_activities', login='pc.coach@example.com')
        self.assertFalse(self._open(self.act_coach_assigned))
        self.assertTrue(self._open(self.act_coach_created))
        self.assertTrue(self._open(self.act_player))
