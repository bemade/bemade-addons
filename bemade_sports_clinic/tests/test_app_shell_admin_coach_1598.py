"""Task 1598 — a coach who is also a system administrator gets the actions
their admin rights allow in the portal app. Synthetic fixtures.

The server-side gates of these actions (``_is_tp_or_system()``,
``_user_can_edit_announcement()``, ``_may_remove_from_team()``) are already
True for ``base.group_system``; the registry key paired with each one in the
template was TP-only, so a coach + system admin saw neither « Ajouter » nor
« Demander » on the team page. Keys flagged ``system`` in the visibility
registry now open for a system admin, whatever their roles.

Acceptance criteria covered here:

* UC-A1 ``sc_can`` (``sc_app_roles.can``): a ``system`` key is visible with
  ``is_system=True`` for a coach role set; never without it; a TP-only key
  that is NOT flagged stays hidden even for a system admin; ``exclude``
  still wins.
* UC-A2 Team page: a coach + system admin gets the « Add a player » card
  (not « Request an addition ») and the announcement compose controls.
* UC-A3 Team page: the « Pending removals » banner is shown to a coach +
  system admin (``_may_remove_from_team`` allows them).
* UC-A4 (dropped) ``players.add_to_team`` is NOT flagged: a system admin
  may open every player, so the players list never shows them a locked row
  — the only place that form renders (asserted in UC-A1 as « not flagged »).
* UC-A5 Player page: a coach + system admin gets the « Remove Player »
  sheet (not the removal request).
* UC-A6 Negative: a plain portal coach is unchanged — request card only, no
  announcement controls, no pending-removals banner, the removal REQUEST
  sheet only.

The persona is an internal system admin (+ the clinic's internal user
group) holding the portal coach group: the role set {coach, internal} of the
report. The ORM refuses portal + internal (the coach group implies
base.group_portal), so the coach group is linked in SQL to reproduce the
role set the report describes. (An internal admin who is only a
head coach by staff row has no injury ACL and is refused the team page
upstream of this fix — not a persona the portal serves.)
"""
from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models import sc_app_roles as registry
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

SYSTEM_KEYS = (
    'team.add_player', 'team.announcement.edit', 'team.pending_removals',
    'patient.remove',
)


@tagged('post_install', '-at_install')
class TestAppShellAdminCoach1598(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        user_g = env.ref('base.group_user').id
        system_g = env.ref('base.group_system').id
        # A system admin of the clinic database also holds the clinic's
        # internal user group (Settings admins are not implied into it).
        clinic_user_g = env.ref('bemade_sports_clinic.group_sports_clinic_user').id
        Users = env['res.users'].with_context(no_reset_password=True)
        cls.admin_coach = Users.create({
            'name': 'T1598 Admin Coach', 'login': 't1598.ac@example.com',
            'password': 't1598-ac-pass',
            'group_ids': [Command.set([user_g, clinic_user_g, system_g])],
        })
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id
        env.cr.execute(
            "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s)",
            (coach_g, cls.admin_coach.id))
        env.invalidate_all()
        env.registry.clear_cache()
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.admin_coach.partner_id.id,
            'role': 'coach',
        })
        cls.team_a.sudo().write({'announcement': 'Synthetic announcement'})
        cls.player_pending = env['sports.patient'].create({
            'first_name': 'Pia', 'last_name': 'Pending',
            'team_ids': [Command.set([cls.team_a.id])],
        })
        cls.player_pending.sudo().write({'pending_removal': True})
        cls.team_url = '/my/team?team_id=%s' % cls.team_a.id
        cls.player_url = '/my/player?player_id=%s&team_id=%s' % (cls.player.id, cls.team_a.id)

    def _admins(self):
        return (
            (self.admin_coach, 't1598.ac@example.com', 't1598-ac-pass'),
        )

    @staticmethod
    def _panel(tree, key):
        nodes = tree.xpath('//section[@data-sc-tab-panel="%s"]' % key)
        return nodes[0] if nodes else None

    # -- UC-A1 -----------------------------------------------------------
    def test_personas_role_sets(self):
        self.assertEqual(self.admin_coach._sc_app_roles(), frozenset({'coach', 'internal'}))

    def test_sc_can_system_keys(self):
        coach_roles = frozenset({'coach', 'internal'})
        for key in SYSTEM_KEYS:
            self.assertTrue(registry.can(key, coach_roles, is_system=True), key)
            self.assertFalse(registry.can(key, coach_roles), key)
            self.assertFalse(registry.can(key, frozenset({'coach'})), key)
        # Not flagged: stays TP-only even for a system admin.
        for key in ('players.create', 'players.add_to_team', 'patient.allergies', 'notes.add',
                    'injury.delete'):
            self.assertFalse(registry.can(key, coach_roles, is_system=True), key)
        # exclude still wins.
        spec = dict(registry.VISIBILITY_REGISTRY['team.add_player'], exclude=frozenset({'coach'}))
        with patch.dict(registry.VISIBILITY_REGISTRY, {'team.add_player': spec}):
            self.assertFalse(registry.can('team.add_player', coach_roles, is_system=True))

    # -- UC-A2 -----------------------------------------------------------
    def test_team_page_add_and_announcement(self):
        self._switch(True)
        for user, login, password in self._admins():
            self.authenticate(login, password)
            _text, tree = self._get(self.team_url)
            self.assertIsNotNone(self._shell(tree), user.name)
            panel = self._panel(tree, 'players')
            self.assertTrue(panel.xpath('.//details[@data-sc-section="team.add_player"]'), user.name)
            self.assertFalse(panel.xpath('.//details[@data-sc-section="team.request_add"]'), user.name)
            self.assertTrue(tree.xpath('//*[@data-sc-section="team.announcement.edit"]'), user.name)

    # -- UC-A3 -----------------------------------------------------------
    def test_team_page_pending_removals_banner(self):
        self._switch(True)
        for user, login, password in self._admins():
            self.authenticate(login, password)
            text, _tree = self._get(self.team_url + '&tab=players')
            self.assertIn('Pending removals', text, user.name)

    # -- UC-A5 -----------------------------------------------------------
    def test_player_page_remove(self):
        self._switch(True)
        for user, login, password in self._admins():
            self.authenticate(login, password)
            _text, tree = self._get(self.player_url)
            form = tree.xpath('//dialog[@id="sc_remove_player_sheet"]//form')
            self.assertTrue(form, user.name)
            self.assertEqual(form[0].get('action'), '/my/team/%s/player/%s/remove'
                             % (self.team_a.id, self.player.id))

    # -- UC-A6 -----------------------------------------------------------
    def test_plain_coach_unchanged(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get(self.team_url)
        panel = self._panel(tree, 'players')
        self.assertTrue(panel.xpath('.//details[@data-sc-section="team.request_add"]'))
        self.assertFalse(panel.xpath('.//details[@data-sc-section="team.add_player"]'))
        self.assertFalse(tree.xpath('//*[@data-sc-section="team.announcement.edit"]'))
        self.assertNotIn('Pending removals', text)
        _text, tree = self._get(self.player_url)
        self.assertFalse(tree.xpath('//dialog[@id="sc_remove_player_sheet"]'))
        self.assertTrue(tree.xpath('//dialog[@id="sc_request_removal_sheet"]'))
