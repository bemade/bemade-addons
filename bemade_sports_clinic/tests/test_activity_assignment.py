"""Portal activity assignee list + POST guards (task 1402).

Acceptance criteria (plan 1402):
1. An INTERNAL treatment professional (internal TP group only) sees all TPs in
   the schedule-page dropdown and can create an activity assigned to another
   TP (the POST guard no longer rejects it).
2. A portal TP scheduling on an INJURY sees all TPs, including TPs NOT
   staffing that team; no coaches, no plain portal users, no internal
   non-TP staff.
3. A portal TP scheduling on a NON-injury record sees all TPs — NOT every
   user in the database.
4. A coach / plain portal user sees only themselves; a POST assigning to
   anyone else is rejected (unchanged behaviour).
5. POST guard: a forged request assigning to a coach's user id is rejected
   even when the requester is a TP.
6. The advisory access warning data is rendered: the off-team TP's option
   carries data-team-access="0", the on-team TP's "1"; assigning to the
   off-team TP still saves (warning never blocks).
7. Regression: the list page's reassign modal and the edit page still offer
   both TP groups (the two already-correct sites are unchanged).

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

    def _post_activity(self, model, res_id, assignee, summary):
        return self.url_open('/my/activity/save', data={
            'csrf_token': self._csrf(),
            'model': model, 'res_id': res_id,
            'activity_type_id': self.todo_type.id,
            'summary': summary, 'user_id': assignee.id,
            'date_deadline': '2026-12-31',
        })

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
        self.assertNotIn('PC Coach', select)

        resp = self._post_activity(
            'sports.patient', self.player.id, self.tp, 'internal-tp-assigns-other')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self._activity_exists('internal-tp-assigns-other'),
                        "internal TP assigning to another TP must succeed")

    # -- 2. portal TP on an injury ----------------------------------------

    def test_portal_tp_injury_dropdown_all_tps_no_coaches(self):
        self._login_tp()
        resp = self.url_open(
            f'/my/activity/create?model=sports.patient.injury&res_id={self.injury.id}')
        self.assertEqual(resp.status_code, 200)
        select = self._assignee_select(resp.text)
        self.assertIn('PC TP', select)
        self.assertIn('ZZ Offteam TP', select,
                      "off-team TPs must be assignable on an injury")
        self.assertIn('ZZ Internal TP', select)
        self.assertNotIn('PC Coach', select, "coaches must not be assignable")
        self.assertNotIn('PC Plain', select)
        self.assertNotIn('ZZ Other Staff', select,
                         "internal non-TP team staff must not be assignable")

    # -- 3. portal TP on a non-injury record -------------------------------

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
        self.assertNotIn('PC Coach', select)
        self.assertNotIn('ZZ Other Staff', select)

    # -- 4. coach: self only -----------------------------------------------

    def test_coach_dropdown_self_only_and_post_rejected(self):
        self._login_coach()
        resp = self.url_open(
            f'/my/activity/create?model=sports.team&res_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)
        select = self._assignee_select(resp.text)
        self.assertIn('PC Coach', select)
        self.assertNotIn('PC TP', select, "a coach may only self-assign")

        resp = self._post_activity(
            'sports.team', self.team_a.id, self.tp, 'coach-assigns-other')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self._activity_exists('coach-assigns-other'),
                         "a coach assigning to someone else must be rejected")

    def test_coach_can_still_self_assign(self):
        self._login_coach()
        resp = self._post_activity(
            'sports.team', self.team_a.id, self.coach, 'coach-self-assign')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self._activity_exists('coach-self-assign'),
                        "self-assignment must keep working for a coach")

    # -- 5. forged POST: TP assigning to a coach ---------------------------

    def test_tp_post_assigning_to_coach_rejected(self):
        self._login_tp()
        resp = self._post_activity(
            'sports.patient', self.player.id, self.coach, 'tp-assigns-coach')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self._activity_exists('tp-assigns-coach'),
                         "assigning to a non-TP must be rejected even for a TP")

    # -- 6. advisory warning data ------------------------------------------

    def test_access_map_rendered_and_never_blocks(self):
        self._login_tp()
        resp = self.url_open(
            f'/my/activity/create?model=sports.patient.injury&res_id={self.injury.id}')
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
            'sports.patient.injury', self.injury.id, self.tp_offteam,
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
        self.assertNotIn('PC Coach', select)

    def test_edit_page_offers_both_tp_groups(self):
        self._login_tp()
        resp = self.url_open(f'/my/activity/{self.act_player.id}/edit')
        self.assertEqual(resp.status_code, 200)
        select = self._assignee_select(resp.text)
        self.assertIn('PC TP', select)
        self.assertIn('ZZ Internal TP', select)
        self.assertIn('ZZ Offteam TP', select)
        self.assertNotIn('PC Coach', select)

    def test_reassign_post_still_accepts_internal_tp(self):
        self._login_tp()
        self.url_open('/my/activity/reassign', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_player.id,
            'new_user_id': self.tp_internal.id,
        })
        self.act_player.invalidate_recordset(['user_id'])
        self.assertEqual(self.act_player.user_id, self.tp_internal,
                         "reassigning to an internal TP must keep working")
