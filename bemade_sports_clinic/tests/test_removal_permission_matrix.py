# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Permission matrix for direct player removal (task 1260).

One policy governs BOTH the internal recordset ``remove_from_team`` and the
portal ``portal_remove_player`` route: they share the single predicate
``sports.patient._may_remove_from_team(team)``. These tests drive the policy
server-side, via ``remove_from_team`` with ``.with_user(...)`` and the predicate
directly, for every role/group combination in the acceptance matrix. Both the
INTERNAL treatment-professional group and the PORTAL one are exercised, because
the two are disjoint and the whole point of the task is that a portal therapist
must pass the same check an internal one does.

The portal HTTP POST itself is browser-driven and verified by UAT on staging
(see the dev-review artifact); it is not asserted here.

Fixtures are synthetic throughout: invented names, no real player data.
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError

INTERNAL_TP = 'bemade_sports_clinic.group_sports_clinic_treatment_professional'
PORTAL_TP = 'bemade_sports_clinic.group_portal_treatment_professional'
PORTAL_COACH = 'bemade_sports_clinic.group_portal_team_coach'


@tagged('post_install', '-at_install')
class TestRemovalPermissionMatrix(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'Matrix Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'Matrix Team', 'parent_id': cls.org.id})
        cls.other_team = env['sports.team'].create({'name': 'Matrix Other Team', 'parent_id': cls.org.id})
        # A team can have only one head therapist, so the internal head-therapist
        # persona gets its own team to sit on.
        cls.ihead_team = env['sports.team'].create({'name': 'Matrix IHead Team', 'parent_id': cls.org.id})

        # Isolate the permission POLICY (groups + roles) from record VISIBILITY:
        # give the tested groups blanket read on the three models the predicate
        # and membership check touch. There are no global (group-less) rules on
        # these models, so a permissive group rule cleanly widens reads. Team
        # visibility is a separate concern, enforced by _check_team_access on the
        # portal, not by this policy.
        for model in ('sports.patient', 'sports.team', 'sports.team.staff'):
            model_id = env['ir.model']._get_id(model)
            env['ir.rule'].create({
                'name': 'Test 1260: blanket read %s' % model,
                'model_id': model_id,
                'domain_force': '[(1, "=", 1)]',
                'groups': [(6, 0, [
                    env.ref(INTERNAL_TP).id,
                    env.ref(PORTAL_TP).id,
                    env.ref(PORTAL_COACH).id,
                ])],
                'perm_read': True,
                'perm_write': False,
                'perm_create': False,
                'perm_unlink': False,
            })

        base_user = env.ref('base.group_user').id
        internal_user = env.ref('bemade_sports_clinic.group_sports_clinic_user').id
        portal = env.ref('base.group_portal').id
        internal_tp = env.ref(INTERNAL_TP).id
        portal_tp = env.ref(PORTAL_TP).id
        coach_g = env.ref(PORTAL_COACH).id

        def _user(name, login, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'email': '%s@example.com' % login,
                'group_ids': [(6, 0, groups)],
            })

        def _staff(user, role, team=None):
            env['sports.team.staff'].create({
                'team_id': (team or cls.team).id,
                'partner_id': user.partner_id.id,
                'role': role,
            })

        cls.admin_user = env.ref('base.user_admin')

        # Internal treatment professionals (internal TP group).
        cls.internal_therapist = _user('Int Therapist', 'mtx_int_ther', [base_user, internal_user, internal_tp])
        _staff(cls.internal_therapist, 'therapist')
        cls.internal_head_therapist = _user('Int Head Therapist', 'mtx_int_head', [base_user, internal_user, internal_tp])
        _staff(cls.internal_head_therapist, 'head_therapist', team=cls.ihead_team)

        # Portal treatment professionals (portal TP group -- DISJOINT from the
        # internal group). This is the population the naive fix would break.
        cls.portal_therapist = _user('Portal Therapist', 'mtx_por_ther', [portal, portal_tp])
        _staff(cls.portal_therapist, 'therapist')
        cls.portal_head_therapist = _user('Portal Head Therapist', 'mtx_por_head', [portal, portal_tp])
        _staff(cls.portal_head_therapist, 'head_therapist')

        # A portal TP who is a therapist on OTHER team only -- proves team scope.
        cls.tp_wrong_team = _user('Portal TP Wrong Team', 'mtx_por_wrong', [portal, portal_tp])
        _staff(cls.tp_wrong_team, 'therapist', team=cls.other_team)

        # A doctor who HOLDS a TP group (passes the group gate) but whose role is
        # excluded -- proves the role allow-list, not just the group, gates.
        cls.doctor_user = _user('Portal Doctor', 'mtx_doctor', [portal, portal_tp])
        _staff(cls.doctor_user, 'doctor')

        # Non-therapist staff roles.
        cls.coach_user = _user('Coach', 'mtx_coach', [portal, coach_g])
        _staff(cls.coach_user, 'coach')
        cls.head_coach_user = _user('Head Coach', 'mtx_head_coach', [portal, coach_g])
        _staff(cls.head_coach_user, 'head_coach')
        cls.other_user = _user('Other Staff', 'mtx_other', [portal, coach_g])
        _staff(cls.other_user, 'other')

        # A plain user with no clinic groups and no staff row.
        cls.regular_user = _user('Regular', 'mtx_regular', [base_user])

        # A fresh player on the team for each test (created per-test to avoid
        # cross-test roster mutation).

    def _player(self, teams=None):
        teams = teams or self.team
        p = self.env['sports.patient'].create({
            'first_name': 'Matrix', 'last_name': 'Player',
        })
        p.team_ids = [(6, 0, teams.ids)]
        return p

    def _assert_removed(self, player, user, team=None):
        team = team or self.team
        player.with_user(user).remove_from_team(team.id)
        player.invalidate_recordset(['team_ids'])
        self.assertNotIn(team, player.team_ids)

    def _assert_denied(self, player, user, team=None):
        team = team or self.team
        with self.assertRaises(AccessError):
            player.with_user(user).remove_from_team(team.id)
        player.invalidate_recordset(['team_ids'])
        self.assertIn(team, player.team_ids, "denied removal must not mutate the roster")

    # ------------------------------------------------------------------
    # AC1 -- head_therapist on the team CAN remove (the live bug this task fixes)
    # ------------------------------------------------------------------
    def test_ac1_internal_head_therapist_can_remove(self):
        player = self._player(teams=self.ihead_team)
        self._assert_removed(player, self.internal_head_therapist, team=self.ihead_team)

    def test_ac1_portal_head_therapist_can_remove(self):
        self._assert_removed(self._player(), self.portal_head_therapist)

    # ------------------------------------------------------------------
    # AC2 -- therapist on the team CAN remove
    # ------------------------------------------------------------------
    def test_ac2_internal_therapist_can_remove(self):
        self._assert_removed(self._player(), self.internal_therapist)

    def test_ac2_portal_therapist_can_remove(self):
        self._assert_removed(self._player(), self.portal_therapist)

    # ------------------------------------------------------------------
    # AC3 -- coach / head_coach / other on the team CANNOT
    # ------------------------------------------------------------------
    def test_ac3_coach_cannot_remove(self):
        self._assert_denied(self._player(), self.coach_user)

    def test_ac3_head_coach_cannot_remove(self):
        self._assert_denied(self._player(), self.head_coach_user)

    def test_ac3_other_role_cannot_remove(self):
        self._assert_denied(self._player(), self.other_user)

    # ------------------------------------------------------------------
    # AC4 -- doctor on the team CANNOT (behaviour change, asserted deliberately)
    # ------------------------------------------------------------------
    def test_ac4_doctor_cannot_remove(self):
        # Holds a TP group, so passes the group gate; role 'doctor' is not in
        # REMOVAL_ROLES, so the role gate denies.
        self._assert_denied(self._player(), self.doctor_user)

    # ------------------------------------------------------------------
    # AC5 -- a TP who is a therapist on a DIFFERENT team CANNOT remove here
    # ------------------------------------------------------------------
    def test_ac5_tp_not_on_this_team_cannot_remove(self):
        self._assert_denied(self._player(), self.tp_wrong_team)

    def test_ac5_tp_can_remove_from_own_team(self):
        # Same user, own team: proves the AC5 denial is team-scope, not a blanket
        # denial of the user.
        player = self._player(teams=self.other_team)
        self._assert_removed(player, self.tp_wrong_team, team=self.other_team)

    # ------------------------------------------------------------------
    # AC6 -- base.group_system CAN remove regardless of role (no staff row)
    # ------------------------------------------------------------------
    def test_ac6_admin_can_remove(self):
        self._assert_removed(self._player(), self.admin_user)

    # ------------------------------------------------------------------
    # AC7 -- portal TP therapist CAN remove (the disjoint-group case, explicit)
    # ------------------------------------------------------------------
    def test_ac7_portal_tp_group_therapist_can_remove(self):
        self.assertTrue(
            self.env.ref(PORTAL_TP) in self.portal_therapist.group_ids,
            "guard: this persona must hold ONLY the portal TP group",
        )
        self.assertFalse(
            self.portal_therapist.has_group(INTERNAL_TP),
            "guard: the two TP groups are disjoint -- portal therapist must NOT "
            "hold the internal group",
        )
        self._assert_removed(self._player(), self.portal_therapist)

    # ------------------------------------------------------------------
    # Non-TP, non-staff user is denied.
    # ------------------------------------------------------------------
    def test_regular_user_cannot_remove(self):
        self._assert_denied(self._player(), self.regular_user)

    # ------------------------------------------------------------------
    # The predicate itself, exercised directly (single source of truth).
    # ------------------------------------------------------------------
    def test_predicate_matches_matrix(self):
        player = self._player()
        may = lambda u, team=self.team: player.with_user(u)._may_remove_from_team(team)
        # Allowed against self.team.
        self.assertTrue(may(self.admin_user))
        self.assertTrue(may(self.internal_therapist))
        self.assertTrue(may(self.portal_therapist))
        self.assertTrue(may(self.portal_head_therapist))
        # Allowed only against their OWN team.
        self.assertTrue(may(self.internal_head_therapist, self.ihead_team))
        self.assertTrue(may(self.tp_wrong_team, self.other_team))
        # Denied against self.team.
        self.assertFalse(may(self.doctor_user))
        self.assertFalse(may(self.coach_user))
        self.assertFalse(may(self.head_coach_user))
        self.assertFalse(may(self.other_user))
        self.assertFalse(may(self.tp_wrong_team))  # therapist elsewhere, not here
        self.assertFalse(may(self.internal_head_therapist))  # head therapist elsewhere
        self.assertFalse(may(self.regular_user))

    # ------------------------------------------------------------------
    # AC8 / AC9 -- the request -> head-therapist round trip (broken today)
    # ------------------------------------------------------------------
    def test_ac9_coach_can_still_request_removal(self):
        player = self._player()
        result = player.with_user(self.coach_user).with_context(lang='en_US').request_team_removal(
            self.team.id, reason='Relocating',
        )
        player.invalidate_recordset(['pending_removal'])
        self.assertTrue(player.pending_removal, "coach must still be able to REQUEST removal")
        self.assertEqual(result['type'], 'ir.actions.client')

    def test_ac8_request_then_head_therapist_actions_it(self):
        player = self._player()

        # 1. Coach requests removal (cannot remove directly -- AC3).
        player.with_user(self.coach_user).with_context(lang='en_US').request_team_removal(
            self.team.id, reason='Relocating',
        )
        player.invalidate_recordset(['pending_removal'])
        self.assertTrue(player.pending_removal)

        # 2. The cron routes an activity to the team's head therapist.
        self.env['sports.patient']._cron_handle_pending_removals()
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'sports.patient'),
            ('res_id', '=', player.id),
            ('summary', 'ilike', 'Player Removal Request'),
        ])
        self.assertTrue(activity, "the cron must create a review activity")
        self.assertEqual(
            activity.user_id, self.portal_head_therapist,
            "the removal activity must land on the team's head therapist",
        )

        # 3. The head therapist actions it: direct removal now SUCCEEDS (this is
        #    the workflow that dead-ended in AccessError before task 1260).
        self._assert_removed(player, self.portal_head_therapist)

    # ------------------------------------------------------------------
    # AC13 -- removal sends no outgoing mail (neutralized DB): the chatter post
    # must not enqueue a mail.mail.
    # ------------------------------------------------------------------
    def test_ac13_removal_sends_no_mail(self):
        player = self._player()
        before = self.env['mail.mail'].search_count([])
        player.with_user(self.internal_therapist).remove_from_team(self.team.id)
        self.assertEqual(
            self.env['mail.mail'].search_count([]), before,
            "removal must not enqueue outgoing mail",
        )

    # ------------------------------------------------------------------
    # Membership / team-existence errors are unchanged for an authorized user.
    # ------------------------------------------------------------------
    def test_not_a_member_raises_validation(self):
        player = self._player()
        with self.assertRaises(ValidationError):
            player.with_user(self.admin_user).remove_from_team(self.other_team.id)
