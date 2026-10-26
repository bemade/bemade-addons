"""Task 1714 — a therapist covering another team's event sees the
activities on it. Synthetic fixtures only.

Owner scope (2026-10-26): a user always sees (1) the activities assigned to
them on any record they can open, and (2) all the activities on the events
they are assigned to (``sports.event.assigned_staff_ids``, the coverage).
Others' activities on other teams stay hidden.

Acceptance criteria:

* AC-1 Therapist T (team A) is assigned to an event of team B: an activity
  she creates on it (assigned to herself) is saved AND listed — in « My
  Activities », on the event's activities page, readable through the ORM
  (portal mail.activity rule).
* AC-2 On that covered event T also sees another staff member's activity.
* AC-3 An activity assigned to T on an event she is NOT assigned to (a
  record a therapist can open) is listed; one assigned to someone else on
  that event is not.
* AC-4 Negative: therapist C (team C, not assigned) never reads T's
  activity (ORM search, direct read, lists); T never reads team C's
  activities on team C's events she does not cover.
* AC-5 A coach of team B sees it per the existing #1589 rule (only the
  activities assigned to / created by the coach): T's activity stays hidden.
* AC-6 An activity assigned to T on a team-A player shows (unchanged).
* AC-7 The related-record link of a covered-event activity opens the event
  (T may open it); the rule records carry the new domain (the activity rules
  are NOT in a noupdate block — the XML reload applies them; asserted).
"""
from datetime import datetime, timedelta

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestCoveredEventActivities1714(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Users = env['res.users'].with_context(no_reset_password=True)
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id
        cls.team_c = env['sports.team'].create({'name': 'PC Team C', 'parent_id': cls.org.id})
        cls.tp_c = Users.create({'name': 'CV TP C', 'login': 'cv.tpc@example.com', 'password': 'cv-tpc',
                                 'group_ids': [Command.set([portal, tp_g])]})
        env['sports.team.staff'].create({'team_id': cls.team_c.id, 'partner_id': cls.tp_c.partner_id.id,
                                         'role': 'therapist'})
        cls.coach_b = Users.create({'name': 'CV Coach B', 'login': 'cv.coachb@example.com',
                                    'password': 'cv-coachb', 'group_ids': [Command.set([portal, coach_g])]})
        env['sports.team.staff'].create({'team_id': cls.team_b.id, 'partner_id': cls.coach_b.partner_id.id,
                                         'role': 'coach'})
        start = datetime(2026, 3, 3, 18, 0)
        cls.event_b = env['sports.event'].create({
            'name': 'CV Covered B', 'event_type': 'game', 'team_ids': [Command.set([cls.team_b.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2), 'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        cls.event_c = env['sports.event'].create({
            'name': 'CV Uncovered C', 'event_type': 'game', 'team_ids': [Command.set([cls.team_c.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2), 'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp_c.id])],
        })
        todo = env.ref('mail.mail_activity_data_todo')

        def _act(record, summary, user):
            return env['mail.activity'].create({
                'res_model_id': env['ir.model']._get(record._name).id, 'res_id': record.id,
                'activity_type_id': todo.id, 'summary': summary, 'user_id': user.id,
            })
        cls.todo = todo
        cls.act_b_other = _act(cls.event_b, 'CV coach task on covered event', cls.coach_b)
        cls.act_c_own = _act(cls.event_c, 'CV team C task', cls.tp_c)
        cls.act_c_mine = _act(cls.event_c, 'CV mine on uncovered event', cls.tp)

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _post(self, url, **data):
        data['csrf_token'] = self._csrf()
        return self.url_open(url, data=data, allow_redirects=False)

    def _create_on_covered(self):
        self._login_tp()
        resp = self._post('/my/activity/save', model='sports.event', res_id=self.event_b.id,
                          activity_type_id=self.todo.id, summary='CV created on covered event',
                          user_id=self.tp.id, date_deadline='2031-01-02', return_url='/my/activities')
        self.assertIn(resp.status_code, (302, 303))
        created = self.env['mail.activity'].search([('summary', '=', 'CV created on covered event')])
        self.assertEqual(len(created), 1)
        return created

    def _listed(self, url, activity):
        _text, tree = self._get(url)
        return bool(tree.xpath('//*[@data-sc-activity-id="%s"]' % activity.id)) or \
            activity.summary in _text

    def _orm_sees(self, user, activity):
        return activity in self.env['mail.activity'].with_user(user).search([('id', '=', activity.id)])

    # -- AC-1 / AC-2 / AC-7 ------------------------------------------------
    def test_created_on_covered_event_is_listed(self):
        created = self._create_on_covered()
        self.assertTrue(self._orm_sees(self.tp, created))
        self.assertTrue(self._listed('/my/activities', created))
        self.assertTrue(self._listed('/my/event/activities?event_id=%s' % self.event_b.id, created))
        # AC-2: the other staff member's activity on the covered event.
        self.assertTrue(self._orm_sees(self.tp, self.act_b_other))
        self.assertTrue(self._listed('/my/event/activities?event_id=%s' % self.event_b.id, self.act_b_other))
        # AC-7: its related link opens the event.
        _text, tree = self._get('/my/event/activities?event_id=%s' % self.event_b.id)
        self.assertTrue(tree.xpath('//a[@href="/my/event/%s"]' % self.event_b.id))

    # -- AC-3 --------------------------------------------------------------
    def test_assigned_to_me_on_uncovered_event(self):
        self._login_tp()
        self.assertTrue(self._orm_sees(self.tp, self.act_c_mine))
        self.assertTrue(self._listed('/my/activities', self.act_c_mine))
        self.assertFalse(self._orm_sees(self.tp, self.act_c_own))
        self.assertFalse(self._listed('/my/event/activities?event_id=%s' % self.event_c.id, self.act_c_own))

    # -- AC-4 --------------------------------------------------------------
    def test_other_team_therapist_never_sees_it(self):
        created = self._create_on_covered()
        self.assertFalse(self._orm_sees(self.tp_c, created))
        self.assertFalse(self._orm_sees(self.tp_c, self.act_b_other))
        with mute_logger('odoo.addons.base.models.ir_rule'), self.assertRaises(AccessError):
            created.with_user(self.tp_c).read(['summary'])
        self.authenticate('cv.tpc@example.com', 'cv-tpc')
        self.assertFalse(self._listed('/my/activities', created))

    # -- AC-5 --------------------------------------------------------------
    def test_coach_of_event_team_existing_rule(self):
        created = self._create_on_covered()
        self.assertFalse(self._orm_sees(self.coach_b, created))
        self.assertTrue(self._orm_sees(self.coach_b, self.act_b_other))

    # -- AC-6 --------------------------------------------------------------
    def test_assigned_on_own_team_player_unchanged(self):
        self._login_tp()
        self.assertTrue(self._orm_sees(self.tp, self.act_player))
        self.assertTrue(self._listed('/my/activities', self.act_player))
        # Team B's player activity (not covered, not mine) stays hidden.
        other = self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get('sports.patient').id, 'res_id': self.player_b.id,
            'activity_type_id': self.todo.id, 'summary': 'CV team B player task', 'user_id': self.coach_b.id,
        })
        self.assertFalse(self._orm_sees(self.tp, other))

    # -- AC-7 --------------------------------------------------------------
    def test_rule_domain_and_not_noupdate(self):
        rule = self.env.ref('bemade_sports_clinic.mail_activity_portal_treatment_professional_rule')
        self.assertIn('sc_assigned_event_ids', rule.domain_force)
        data = self.env['ir.model.data'].search([
            ('module', '=', 'bemade_sports_clinic'),
            ('name', '=', 'mail_activity_portal_treatment_professional_rule')])
        self.assertFalse(data.noupdate)
