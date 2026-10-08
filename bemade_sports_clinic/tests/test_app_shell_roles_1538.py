"""Task 1538 — portal app shell: multi-role resolution and the declarative
registries (nav + visibility). Synthetic fixtures only.

Acceptance criteria covered here:

* UC-R1 A user's roles are resolved as a SET from groups and staff rows
  (coach, head_coach, therapist, head_therapist, doctor, clinic_admin,
  internal); nothing in the templates branches on groups.
* UC-R2 Nav visibility = union of ``include`` over the user's roles minus any
  ``exclude`` — a coach who is also a therapist sees both roles' entries, and
  an entry excluded for ``coach`` stays hidden for that same user (exclude
  wins).
* UC-R3 The reserved roles (teacher, parent, player, secretary) resolve to
  nothing today; mapping ``parent`` to a group (test-only) is enough for its
  entries to show / hide as declared — no template edit (AC6).
* UC-R4 ``sc_can(key)`` answers from the visibility registry, raises on an
  unknown key, and every field key hidden from a role is ALSO unreadable for
  that role server-side (the registry decides what is shown, never what is
  allowed).
"""
from unittest.mock import patch

from odoo import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.models import sc_app_roles as registry


@tagged('post_install', '-at_install')
class TestAppShellRoles1538(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.team = env['sports.team'].create({'name': 'Roles Team'})
        portal = env.ref('base.group_portal').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id

        def _user(login, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': login, 'login': '%s@example.com' % login,
                'group_ids': [Command.set(groups)],
            })

        cls.coach = _user('roles.coach', [portal, coach_g])
        cls.tp = _user('roles.tp', [portal, tp_g])
        cls.both = _user('roles.both', [portal, coach_g, tp_g])
        cls.plain = _user('roles.plain', [portal])
        cls.head_coach = _user('roles.headcoach', [portal, coach_g])
        env['sports.team.staff'].create({
            'team_id': cls.team.id, 'partner_id': cls.head_coach.partner_id.id,
            'role': 'head_coach',
        })
        # A test-only group standing in for a future « parent » role.
        cls.parent_group = env['res.groups'].create({'name': 'Test parent 1538'})
        env['ir.model.data'].create({
            'module': 'bemade_sports_clinic', 'name': 'test_group_parent_1538',
            'model': 'res.groups', 'res_id': cls.parent_group.id,
        })
        cls.parent = _user('roles.parent', [portal, cls.parent_group.id])
        cls.coach_parent = _user('roles.coachparent', [portal, coach_g, cls.parent_group.id])

    # -- UC-R1 -----------------------------------------------------------
    def test_roles_resolved_as_a_set(self):
        self.assertEqual(self.coach._sc_app_roles(), frozenset({'coach'}))
        self.assertEqual(self.tp._sc_app_roles(), frozenset({'therapist'}))
        self.assertEqual(self.both._sc_app_roles(), frozenset({'coach', 'therapist'}))
        self.assertEqual(self.plain._sc_app_roles(), frozenset())
        self.assertEqual(self.head_coach._sc_app_roles(), frozenset({'coach', 'head_coach'}))
        admin_roles = self.env.ref('base.user_admin')._sc_app_roles()
        self.assertIn('internal', admin_roles)

    def test_app_roles_exclude_internal_only(self):
        """A plain internal user (no clinic role) is not an app user."""
        self.assertFalse(frozenset({'internal'}) & registry.APP_ROLES)
        self.assertTrue(frozenset({'coach'}) & registry.APP_ROLES)
        for reserved in registry.RESERVED_ROLES:
            self.assertIn(reserved, registry.APP_ROLES)

    # -- UC-R2 -----------------------------------------------------------
    def _keys(self, roles, placement, ctx=None):
        return [e['key'] for e in registry.visible_nav(roles, placement, ctx or {})]

    def test_tabs_union_of_roles(self):
        coach_tabs = self._keys(self.coach._sc_app_roles(), 'tab')
        tp_tabs = self._keys(self.tp._sc_app_roles(), 'tab')
        both_tabs = self._keys(self.both._sc_app_roles(), 'tab')
        self.assertEqual(coach_tabs, ['teams', 'players', 'activities', 'more'])
        self.assertEqual(tp_tabs, ['teams', 'players', 'clinic', 'activities', 'more'])
        self.assertEqual(both_tabs, tp_tabs)
        self.assertEqual(self._keys(self.plain._sc_app_roles(), 'tab'), [])

    def test_exclude_wins_over_include(self):
        entry = {
            'key': 'test_tp_not_coach', 'label': 'x', 'icon': 'more', 'url': '/x',
            'include': frozenset({'therapist'}), 'exclude': frozenset({'coach'}),
            'requires': None, 'placement': ('tab',), 'sequence': 35,
        }
        with patch.object(registry, 'NAV_REGISTRY', registry.NAV_REGISTRY + (entry,)):
            self.assertIn('test_tp_not_coach', self._keys(self.tp._sc_app_roles(), 'tab'))
            self.assertNotIn('test_tp_not_coach', self._keys(self.both._sc_app_roles(), 'tab'))
            self.assertNotIn('test_tp_not_coach', self._keys(self.coach._sc_app_roles(), 'tab'))

    def test_requires_gates_bookings(self):
        roles = self.tp._sc_app_roles()
        self.assertNotIn('bookings', self._keys(roles, 'rail', {'booking_card_enable': False}))
        self.assertIn('bookings', self._keys(roles, 'rail', {'booking_card_enable': True}))
        self.assertIn('bookings', self._keys(roles, 'plus', {'booking_card_enable': True}))
        # Never a phone tab: bookings live under « Plus » on the phone.
        self.assertNotIn('bookings', self._keys(roles, 'tab', {'booking_card_enable': True}))

    # -- UC-R3 -----------------------------------------------------------
    def test_reserved_roles_resolve_to_nothing_today(self):
        for reserved in ('teacher', 'parent', 'player', 'secretary'):
            self.assertIn(reserved, registry.RESERVED_ROLES)
            self.assertEqual(tuple(registry.ROLE_GROUPS.get(reserved, ())), ())
        self.assertEqual(self.parent._sc_app_roles(), frozenset())

    def test_parent_mapping_is_data_only(self):
        parent_entry = {
            'key': 'test_parent_kids', 'label': 'x', 'icon': 'players', 'url': '/x',
            'include': frozenset({'parent'}), 'exclude': frozenset(),
            'requires': None, 'placement': ('tab',), 'sequence': 25,
        }
        no_parent_entry = {
            'key': 'test_not_parent', 'label': 'y', 'icon': 'more', 'url': '/y',
            'include': frozenset({'coach'}), 'exclude': frozenset({'parent'}),
            'requires': None, 'placement': ('tab',), 'sequence': 26,
        }
        mapping = {'parent': ('bemade_sports_clinic.test_group_parent_1538',)}
        with patch.dict(registry.ROLE_GROUPS, mapping), \
                patch.object(registry, 'NAV_REGISTRY',
                             registry.NAV_REGISTRY + (parent_entry, no_parent_entry)):
            self.assertEqual(self.parent._sc_app_roles(), frozenset({'parent'}))
            parent_tabs = self._keys(self.parent._sc_app_roles(), 'tab')
            # The parent sees its own entry + « Plus » (declared for every app role).
            self.assertEqual(parent_tabs, ['test_parent_kids', 'more'])
            coach_parent_tabs = self._keys(self.coach_parent._sc_app_roles(), 'tab')
            self.assertIn('test_parent_kids', coach_parent_tabs)
            self.assertIn('teams', coach_parent_tabs)
            self.assertNotIn('test_not_parent', coach_parent_tabs)
            self.assertIn('test_not_parent', self._keys(self.coach._sc_app_roles(), 'tab'))

    # -- UC-R4 -----------------------------------------------------------
    def test_sc_can_matches_registry(self):
        coach_roles = self.coach._sc_app_roles()
        tp_roles = self.tp._sc_app_roles()
        self.assertFalse(registry.can('patient.allergies', coach_roles))
        self.assertTrue(registry.can('patient.allergies', tp_roles))
        self.assertTrue(registry.can('home.team_status', coach_roles))
        self.assertFalse(registry.can('home.clinic_teaser', coach_roles))
        self.assertTrue(registry.can('home.clinic_teaser', tp_roles))
        with self.assertRaises(KeyError):
            registry.can('no.such.key', tp_roles)

    def test_hidden_field_keys_are_denied_by_acl(self):
        """Every field key hidden from a role is unreadable for that role."""
        personas = {'coach': self.coach, 'therapist': self.tp}
        checked = 0
        for key, spec in registry.VISIBILITY_REGISTRY.items():
            if not spec.get('field'):
                continue
            model = self.env[spec['model']]
            field = model._fields[spec['field']]
            for role, user in personas.items():
                shown = registry.can(key, user._sc_app_roles())
                readable = model.with_user(user)._has_field_access(field, 'read')
                if not shown:
                    self.assertFalse(
                        readable, "%s is hidden from %s but readable" % (key, role))
                    checked += 1
        self.assertGreaterEqual(checked, 4)
