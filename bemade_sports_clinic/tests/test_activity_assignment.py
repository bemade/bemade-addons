"""Portal activity assignee list + POST guards (task 1402).

Acceptance criteria (plan 1402):
1. An INTERNAL treatment professional (internal TP group only) sees all TPs in
   the schedule-page dropdown and can create an activity assigned to another
   TP (the POST guard no longer rejects it).
2. A portal TP scheduling on a PLAYER sees all TPs, including TPs NOT
   staffing that team; no coaches, no plain portal users, no internal
   non-TP staff. (Task 1409: activities are scheduled on the player only —
   the former injury context is gone.)
3. A portal TP scheduling on a NON-injury record sees all TPs — NOT every
   user in the database.
4. Task 1500: a coach sees the STAFF OF THE COACH'S OWN TEAMS (every role
   and source — therapists, the head therapist, the doctor, other coaches —
   plus themselves) and nobody from other teams / organizations nor a TP
   who staffs no team; a POST assigning outside that set is rejected. A
   plain portal user still sees / may assign only themselves.
5. POST guard: a forged request assigning to a plain portal user's id is
   rejected even when the requester is a TP; assigning to a coach is
   accepted (task 1426).
6. The advisory access warning data is rendered: the off-team TP's option
   carries data-team-access="0", the on-team TP's "1"; assigning to the
   off-team TP still saves (warning never blocks).
7. Regression: the list page's reassign modal and the edit page still offer
   both TP groups (the two already-correct sites are unchanged).

8. Task 1408 (follow-up): the PLAYER page and the TEAM page Activities-tab
   add-activity forms offer the same all-TP list to a portal TP (they used a
   plain search() that base.res_users_rule_portal collapsed to "self"); a
   coach gets the task-1500 own-teams-staff list there too.

9. Task 1500: the SAME per-actor rule drives the /my/activities reassign
   modal and the /my/activity/reassign guard (a coach may reassign within
   their teams' staff, never outside), and the edit page assignee select is
   honoured by /my/activity/update — for a TP (any assignable user) and for
   a coach (within rule); outside the rule → error=invalid_user and the
   assignee is unchanged. The TP list is asserted as an EXACT set so the
   coach rule can never leak into it.

(The visual dropdown contents and the warning toggle are browser behaviour —
NOT verified here; see the dev-review UAT walkthrough.)

All fixtures are synthetic (public repo — no real names).
"""
import re

from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestActivityAssignment(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        portal = env.ref('base.group_portal').id
        internal = env.ref('base.group_user').id
        portal_tp_g = env.ref(
            'bemade_sports_clinic.group_portal_treatment_professional').id
        internal_tp_g = env.ref(
            'bemade_sports_clinic.group_sports_clinic_treatment_professional').id

        # Portal TP who staffs NO team (the cross-team / substitute shape).
        cls.tp_offteam = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZZ Offteam TP', 'login': 'zz.offteam.tp@example.com',
            'password': 'zz-offteam-tp',
            'group_ids': [Command.set([portal, portal_tp_g])],
        })

        # INTERNAL treatment professional: clinic internal-user group (which
        # implies base.group_user and carries the clinic model ACLs) + the
        # INTERNAL TP group — but NOT the portal TP group. Staffed on team A
        # so the record checks pass.
        clinic_user_g = env.ref('bemade_sports_clinic.group_sports_clinic_user').id
        cls.tp_internal = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZZ Internal TP', 'login': 'zz.internal.tp@example.com',
            'password': 'zz-internal-tp',
            'group_ids': [Command.set([clinic_user_g, internal_tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id,
            'partner_id': cls.tp_internal.partner_id.id,
            'role': 'therapist',
        })

        # INTERNAL user who is a treatment professional ONLY by implication:
        # the clinic Administrator group implies the internal TP group but
        # the user never carries it directly (the owner's own shape).
        clinic_admin_g = env.ref('bemade_sports_clinic.group_sports_clinic_admin').id
        cls.tp_admin = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZZ Admin TP', 'login': 'zz.admin.tp@example.com',
            'password': 'zz-admin-tp',
            'group_ids': [Command.set([clinic_admin_g])],
        })

        # Internal NON-TP staff member on team A (would have leaked into the
        # old injury team-staff dropdown).
        cls.staff_other = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZZ Other Staff', 'login': 'zz.other.staff@example.com',
            'password': 'zz-other-staff',
            'group_ids': [Command.set([internal])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id,
            'partner_id': cls.staff_other.partner_id.id,
            'role': 'other',
        })

        # -- Task 1500 fixtures: the coach's own team (team A) staff vs a
        # second team (team B) of the same organization. All synthetic.
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id

        def _portal_user(name, login, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': login,
                'group_ids': [Command.set(groups)],
            })

        def _staff(team, user, role):
            return env['sports.team.staff'].create({
                'team_id': team.id, 'partner_id': user.partner_id.id, 'role': role,
            })

        # Team A (the coach's team): head therapist + a second coach.
        cls.head_tp_a = _portal_user(
            'ZZ Head Therapist A', 'zz.head.tp.a@example.com', [portal, portal_tp_g])
        _staff(cls.team_a, cls.head_tp_a, 'head_therapist')
        cls.coach_two_a = _portal_user(
            'ZZ Coach Two A', 'zz.coach.two.a@example.com', [portal, coach_g])
        _staff(cls.team_a, cls.coach_two_a, 'coach')
        # Team A staffer holding NO clinic group at all (role 'other').
        cls.plain_staff_a = _portal_user(
            'ZZ Plain Staff A', 'zz.plain.staff.a@example.com', [portal])
        _staff(cls.team_a, cls.plain_staff_a, 'other')

        # Team B only: a TP and a coach the team-A coach must never see.
        cls.tp_b = _portal_user(
            'ZZ Therapist B', 'zz.tp.b@example.com', [portal, portal_tp_g])
        _staff(cls.team_b, cls.tp_b, 'therapist')
        cls.coach_b = _portal_user(
            'ZZ Coach B', 'zz.coach.b@example.com', [portal, coach_g])
        _staff(cls.team_b, cls.coach_b, 'head_coach')

        # Every fixture persona that is EVER offered as an assignee to a TP
        # (the exact TP set is asserted against this, restricted to the
        # synthetic 'PC '/'ZZ ' names so pre-existing DB users do not leak
        # into the assertion).
        cls.tp_list_fixture_names = {
            'PC TP', 'PC Coach', 'ZZ Offteam TP', 'ZZ Internal TP',
            'ZZ Admin TP', 'ZZ Head Therapist A', 'ZZ Coach Two A',
            'ZZ Therapist B', 'ZZ Coach B',
        }
        # What the team-A coach may assign to: team A staff (any role) + self.
        cls.coach_a_list_names = {
            'PC Coach', 'PC TP', 'ZZ Internal TP', 'ZZ Other Staff',
            'ZZ Head Therapist A', 'ZZ Coach Two A', 'ZZ Plain Staff A',
        }

        cls.todo_type = env.ref('mail.mail_activity_data_todo')

    # -- helpers -----------------------------------------------------------

    def _assignee_select(self, html, name='user_id'):
        """Return the inner HTML of the assignee <select> on a rendered page."""
        m = re.search(
            r'<select[^>]*name="%s"[^>]*>(.*?)</select>' % name, html, re.S)
        self.assertTrue(m, "assignee select '%s' not found in page" % name)
        return m.group(1)

    def _login(self, login, pwd):
        self.authenticate(login, pwd)

    def _option_names(self, select_html):
        """Names of the <option>s of a rendered select (whitespace-trimmed,
        empty placeholder options dropped)."""
        names = re.findall(r'<option\b[^>]*>(.*?)</option>', select_html, re.S)
        return {re.sub(r'\s+', ' ', n).strip() for n in names} - {''}

    def _fixture_names(self, names):
        """Restrict a rendered name set to the synthetic fixture personas."""
        return {n for n in names if n.startswith(('PC ', 'ZZ '))}

    def _post_reassign(self, activity, new_user, return_url=None, **kw):
        data = {
            'csrf_token': self._csrf(), 'activity_id': activity.id,
            'new_user_id': new_user.id,
        }
        if return_url:
            data['return_url'] = return_url
        return self.url_open('/my/activity/reassign', data=data, **kw)

    def _post_update(self, activity, new_user):
        return self.url_open('/my/activity/update', data={
            'csrf_token': self._csrf(), 'activity_id': activity.id,
            'activity_type_id': activity.activity_type_id.id,
            'summary': activity.summary, 'note': activity.note or '',
            'date_deadline': str(activity.date_deadline),
            'user_id': new_user.id,
        })

    def _assignee_of(self, activity):
        activity.invalidate_recordset(['user_id'])
        return activity.user_id

    def _post_activity(self, model, res_id, assignee, summary, **kw):
        return self.url_open('/my/activity/save', data={
            'csrf_token': self._csrf(),
            'model': model, 'res_id': res_id,
            'activity_type_id': self.todo_type.id,
            'summary': summary, 'user_id': assignee.id,
            'date_deadline': '2026-12-31',
        }, **kw)

    def _activity_exists(self, summary):
        return bool(self.env['mail.activity'].search_count(
            [('summary', '=', summary)]))

    # -- 1. internal TP ----------------------------------------------------

    def test_internal_tp_sees_all_tps_and_can_assign_others(self):
        self._login('zz.internal.tp@example.com', 'zz-internal-tp')
        resp = self.url_open(
            f'/my/activity/create?model=sports.patient&res_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        select = self._assignee_select(resp.text)
        self.assertIn('PC TP', select)
        self.assertIn('ZZ Offteam TP', select)
        self.assertIn('ZZ Internal TP', select)
        self.assertIn('PC Coach', select, "coaches are assignable (task 1426)")

        resp = self._post_activity(
            'sports.patient', self.player.id, self.tp, 'internal-tp-assigns-other')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self._activity_exists('internal-tp-assigns-other'),
                        "internal TP assigning to another TP must succeed")

    def test_internal_tp_by_implied_group_is_assignable(self):
        """Regression: a user holding the internal TP group only through an
        implying group (clinic Administrator) must be in the picker and be
        an accepted assignee — ``res.users.group_ids`` is the DIRECT groups
        field, so the helper must match on ``all_group_ids``."""
        self._login('zz.internal.tp@example.com', 'zz-internal-tp')
        resp = self.url_open(
            f'/my/activity/create?model=sports.patient&res_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('ZZ Admin TP', self._assignee_select(resp.text))

        resp = self._post_activity(
            'sports.patient', self.player.id, self.tp_admin, 'assign-to-implied-tp')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self._activity_exists('assign-to-implied-tp'),
                        "assigning to a TP-by-implied-group must succeed")

    # -- 2. portal TP on an injury ----------------------------------------

    def test_portal_tp_player_dropdown_all_tps_and_coaches(self):
        self._login_tp()
        resp = self.url_open(
            f'/my/activity/create?model=sports.patient&res_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        select = self._assignee_select(resp.text)
        self.assertIn('PC TP', select)
        self.assertIn('ZZ Offteam TP', select,
                      "off-team TPs must be assignable on a player")
        self.assertIn('ZZ Internal TP', select)
        self.assertIn('PC Coach', select, "coaches are assignable (task 1426)")
        self.assertNotIn('PC Plain', select)
        self.assertNotIn('ZZ Other Staff', select,
                         "internal non-TP team staff must not be assignable")

    # -- 3. portal TP on a non-player record -------------------------------

    def test_portal_tp_team_dropdown_is_tps_not_everyone(self):
        self._login_tp()
        resp = self.url_open(
            f'/my/activity/create?model=sports.team&res_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)
        select = self._assignee_select(resp.text)
        self.assertIn('PC TP', select)
        self.assertIn('ZZ Offteam TP', select)
        self.assertNotIn('PC Plain', select,
                         "the unbounded search([]) must be gone")
        self.assertIn('PC Coach', select, "coaches are assignable (task 1426)")
        self.assertNotIn('ZZ Other Staff', select)

    # -- 4. coach: staff of the coach's own teams (task 1500) ---------------

    def test_coach_dropdown_own_team_staff_and_post_out_of_team_rejected(self):
        """AC1: the create form offers the coach every team-A staffer (the
        therapist, the head therapist, the second coach, the internal TP,
        even the role='other' staffers) and nobody else."""
        self._login_coach()
        for url in (f'/my/activity/create?model=sports.team&res_id={self.team_a.id}',
                    f'/my/activity/create?model=sports.patient&res_id={self.player.id}'):
            resp = self.url_open(url)
            self.assertEqual(resp.status_code, 200, url)
            names = self._fixture_names(
                self._option_names(self._assignee_select(resp.text)))
            self.assertEqual(names, self.coach_a_list_names, url)
            self.assertNotIn('ZZ Therapist B', names, url)
            self.assertNotIn('ZZ Coach B', names, url)
            self.assertNotIn('ZZ Offteam TP', names,
                             "a TP staffing no team is not the coach's staff")
            self.assertNotIn('PC Plain', names, url)

        # POST to a team-B staffer / a no-team TP: rejected, nothing created.
        for assignee, summary in ((self.tp_b, 'coach-assigns-team-b-tp'),
                                  (self.coach_b, 'coach-assigns-team-b-coach'),
                                  (self.tp_offteam, 'coach-assigns-offteam-tp')):
            resp = self._post_activity(
                'sports.team', self.team_a.id, assignee, summary)
            self.assertEqual(resp.status_code, 200)
            self.assertIn('error=invalid_user', resp.url, summary)
            self.assertFalse(self._activity_exists(summary),
                             "a coach assigning outside their teams' staff must be rejected")

    def test_coach_post_assigning_to_own_team_staff_accepted(self):
        """AC1: POSTing to a team-A therapist / head therapist / second
        coach creates the activity with that assignee."""
        self._login_coach()
        for assignee, summary in ((self.tp, 'coach-assigns-tp'),
                                  (self.head_tp_a, 'coach-assigns-head-tp'),
                                  (self.coach_two_a, 'coach-assigns-coach-two')):
            resp = self._post_activity(
                'sports.patient', self.player.id, assignee, summary)
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn('error=', resp.url, summary)
            act = self.env['mail.activity'].search([('summary', '=', summary)])
            self.assertEqual(len(act), 1, summary)
            self.assertEqual(act.user_id, assignee, summary)

    def test_coach_list_reassign_modal_and_reassign_post_follow_rule(self):
        """AC2 + item 9: the /my/activities reassign modal offers the coach
        the team-A staff only; /my/activity/reassign accepts in-rule and
        rejects out-of-rule assignees."""
        self._login_coach()
        resp = self.url_open(
            f'/my/activities?model=sports.team&res_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)
        names = self._fixture_names(self._option_names(
            self._assignee_select(resp.text, name='new_user_id')))
        self.assertEqual(names, self.coach_a_list_names)

        # In rule: accepted.
        resp = self._post_reassign(self.act_team, self.head_tp_a)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._assignee_of(self.act_team), self.head_tp_a,
                         "a coach reassigning to their team's head therapist must succeed")
        # Out of rule: rejected with error=invalid_user, assignee unchanged.
        resp = self._post_reassign(self.act_team, self.tp_b,
                                   return_url='/my/activities')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error=invalid_user', resp.url)
        self.assertEqual(self._assignee_of(self.act_team), self.head_tp_a,
                         "a coach reassigning to another team's TP must be rejected")
        resp = self._post_reassign(self.act_team, self.tp_offteam)
        self.assertEqual(self._assignee_of(self.act_team), self.head_tp_a)

    def test_edit_page_assignee_change_persists_within_rule(self):
        """AC3: the edit page assignee select is honoured by
        /my/activity/update — for a TP (any assignable user) and for a coach
        (team staff); outside the rule the assignee is unchanged and the
        edit page is re-shown with error=invalid_user."""
        # TP: may move the activity to a TP off the team.
        self._login_tp()
        resp = self.url_open(f'/my/activity/{self.act_player.id}/edit')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('assignee_access_warning', resp.text,
                      "the edit page must render the team-access advisory")
        resp = self._post_update(self.act_player, self.tp_offteam)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('error=', resp.url)
        self.assertEqual(self._assignee_of(self.act_player), self.tp_offteam,
                         "a TP's edit-page assignee change must persist")

        # Coach: the edit page offers the team-A staff; in rule persists.
        self._login_coach()
        resp = self.url_open(f'/my/activity/{self.act_team.id}/edit')
        self.assertEqual(resp.status_code, 200)
        names = self._fixture_names(
            self._option_names(self._assignee_select(resp.text)))
        self.assertEqual(names, self.coach_a_list_names)
        resp = self._post_update(self.act_team, self.coach_two_a)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('error=', resp.url)
        self.assertEqual(self._assignee_of(self.act_team), self.coach_two_a,
                         "a coach's in-rule edit-page assignee change must persist")
        # Out of rule: rejected, unchanged.
        resp = self._post_update(self.act_team, self.tp_b)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error=invalid_user', resp.url)
        self.assertIn(f'/my/activity/{self.act_team.id}/edit', resp.url)
        self.assertEqual(self._assignee_of(self.act_team), self.coach_two_a,
                         "an out-of-rule edit-page assignee change must be rejected")

    def test_tp_list_is_exactly_all_tps_and_coaches(self):
        """AC4: the TP list is unchanged by task 1500 — all TPs (portal +
        internal, incl. by implied group) and all coaches, whatever their
        teams; no plain portal users, no internal non-TP staff."""
        self._login_tp()
        for url, name in (
                (f'/my/activity/create?model=sports.patient&res_id={self.player.id}', 'user_id'),
                (f'/my/activity/{self.act_player.id}/edit', 'user_id'),
                (f'/my/activities?model=sports.patient&res_id={self.player.id}', 'new_user_id'),
                (f'/my/player?player_id={self.player.id}', 'user_id'),
                (f'/my/team?team_id={self.team_a.id}', 'user_id')):
            resp = self.url_open(url)
            self.assertEqual(resp.status_code, 200, url)
            names = self._fixture_names(
                self._option_names(self._assignee_select(resp.text, name=name)))
            self.assertEqual(names, self.tp_list_fixture_names, url)

    def test_plain_portal_staffer_still_self_only(self):
        """AC4: a portal user with no clinic group (a role='other' staffer)
        may still only self-assign — a POST to a teammate is rejected on
        save and on reassign. (Redirects are not followed: a user holding no
        clinic group cannot render the team / activities pages, which would
        bounce and mask the error query.)"""
        self._login('zz.plain.staff.a@example.com', 'zz.plain.staff.a@example.com')
        resp = self._post_activity(
            'sports.team', self.team_a.id, self.tp, 'plain-assigns-tp',
            allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertIn('error=invalid_user', resp.headers.get('Location', ''))
        self.assertFalse(self._activity_exists('plain-assigns-tp'))
        resp = self._post_activity(
            'sports.team', self.team_a.id, self.plain_staff_a, 'plain-self-assign',
            allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertNotIn('error=', resp.headers.get('Location', ''))
        self.assertTrue(self._activity_exists('plain-self-assign'),
                        "self-assignment stays allowed for a plain staffer")
        before = self._assignee_of(self.act_team)
        resp = self._post_reassign(self.act_team, self.coach, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertIn('error=invalid_user', resp.headers.get('Location', ''))
        self.assertEqual(self._assignee_of(self.act_team), before,
                         "a plain staffer must not reassign to anyone else")

    def test_coach_can_still_self_assign(self):
        self._login_coach()
        resp = self._post_activity(
            'sports.team', self.team_a.id, self.coach, 'coach-self-assign')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self._activity_exists('coach-self-assign'),
                        "self-assignment must keep working for a coach")

    # -- 5. forged POST: TP assigning to a coach ---------------------------

    def test_tp_post_assigning_to_coach_accepted(self):
        """Task 1426: coaches are assignees — a TP may assign to a coach."""
        self._login_tp()
        resp = self._post_activity(
            'sports.patient', self.player.id, self.coach, 'tp-assigns-coach')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self._activity_exists('tp-assigns-coach'),
                        "assigning to a coach must be accepted for a TP")

    def test_tp_post_assigning_to_plain_portal_user_rejected(self):
        """The forged-POST guard still holds for non-assignable users."""
        self._login_tp()
        resp = self._post_activity(
            'sports.patient', self.player.id, self.plain, 'tp-assigns-plain')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self._activity_exists('tp-assigns-plain'),
                         "assigning to a plain portal user must be rejected")

    # -- 6. advisory warning data ------------------------------------------

    def test_access_map_rendered_and_never_blocks(self):
        self._login_tp()
        resp = self.url_open(
            f'/my/activity/create?model=sports.patient&res_id={self.player.id}')
        html = resp.text
        select = self._assignee_select(html)

        def _access_flag(user):
            # Attribute order is renderer-dependent: find the option tag by its
            # value, then pull data-team-access from anywhere in that tag.
            m = re.search(r'<option\b[^>]*\bvalue="%d"[^>]*>' % user.id, select)
            self.assertTrue(m, "option for %s not found" % user.name)
            a = re.search(r'data-team-access="([01])"', m.group(0))
            self.assertTrue(a, "option for %s lacks data-team-access" % user.name)
            return a.group(1)

        self.assertEqual(_access_flag(self.tp), '1',
                         "on-team TP must be flagged as having access")
        self.assertEqual(_access_flag(self.tp_offteam), '0',
                         "off-team TP must be flagged as lacking access")
        self.assertIn('assignee_access_warning', html,
                      "the advisory warning element must be rendered")

        # The warning is advisory: assigning to the off-team TP still saves.
        resp = self._post_activity(
            'sports.patient', self.player.id, self.tp_offteam,
            'assign-offteam-tp')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self._activity_exists('assign-offteam-tp'),
                        "the access warning must never block the save")

    # -- 7. regression: list + edit sites unchanged ------------------------

    def test_list_reassign_modal_offers_both_tp_groups(self):
        self._login_tp()
        resp = self.url_open(
            f'/my/activities?model=sports.patient&res_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        select = self._assignee_select(resp.text, name='new_user_id')
        self.assertIn('PC TP', select)
        self.assertIn('ZZ Internal TP', select)
        self.assertIn('ZZ Offteam TP', select)
        self.assertIn('PC Coach', select, "coaches are assignable (task 1426)")

    def test_edit_page_offers_both_tp_groups(self):
        self._login_tp()
        resp = self.url_open(f'/my/activity/{self.act_player.id}/edit')
        self.assertEqual(resp.status_code, 200)
        select = self._assignee_select(resp.text)
        self.assertIn('PC TP', select)
        self.assertIn('ZZ Internal TP', select)
        self.assertIn('ZZ Offteam TP', select)
        self.assertIn('PC Coach', select, "coaches are assignable (task 1426)")

    def test_reassign_post_still_accepts_internal_tp(self):
        self._login_tp()
        self.url_open('/my/activity/reassign', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_player.id,
            'new_user_id': self.tp_internal.id,
        })
        self.act_player.invalidate_recordset(['user_id'])
        self.assertEqual(self.act_player.user_id, self.tp_internal,
                         "reassigning to an internal TP must keep working")

    # -- 8. task 1408: player page + team page Activities tabs ---------------

    def test_player_page_activities_tab_offers_all_tps(self):
        """The owner's spot: /my/player → Activities tab add-activity form."""
        self._login_tp()
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        select = self._assignee_select(resp.text)
        self.assertIn('PC TP', select)
        self.assertIn('ZZ Offteam TP', select,
                      "portal TP off this team must be offered (was self-only)")
        self.assertIn('ZZ Internal TP', select,
                      "internal TP must be offered too")
        self.assertIn('PC Coach', select, "coaches are assignable (task 1426)")
        self.assertNotIn('PC Plain', select)
        self.assertNotIn('ZZ Other Staff', select)

    def test_team_page_activities_tab_offers_all_tps(self):
        self._login_tp()
        resp = self.url_open(f'/my/team?team_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)
        select = self._assignee_select(resp.text)
        self.assertIn('PC TP', select)
        self.assertIn('ZZ Offteam TP', select)
        self.assertIn('ZZ Internal TP', select)
        self.assertIn('PC Coach', select, "coaches are assignable (task 1426)")
        self.assertNotIn('PC Plain', select)

    def test_player_and_team_pages_coach_own_team_staff(self):
        """AC1/AC2 (task 1500): the player-page and team-page Activities
        tabs offer the coach the team-A staff (add form AND reassign modal),
        never team-B staff or a no-team TP."""
        self._login_coach()
        for url in (f'/my/player?player_id={self.player.id}',
                    f'/my/team?team_id={self.team_a.id}'):
            resp = self.url_open(url)
            self.assertEqual(resp.status_code, 200, url)
            names = self._fixture_names(
                self._option_names(self._assignee_select(resp.text)))
            self.assertEqual(names, self.coach_a_list_names, url)
            self.assertNotIn('ZZ Therapist B', names, url)
            self.assertNotIn('ZZ Offteam TP', names, url)
        # Team page reassign modal (task 1223 activity_list_table) — same list.
        resp = self.url_open(f'/my/team?team_id={self.team_a.id}')
        modal = self._assignee_select(resp.text, name='new_user_id')
        self.assertEqual(self._fixture_names(self._option_names(modal)),
                         self.coach_a_list_names)
