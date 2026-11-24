# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Hook 1 — roles. Synthetic roles only.

Acceptance criteria:

* UC-K1 ``res.users._pk_roles()`` is the SET of the roles whose ``groups``
  (any-of) the user holds, united with ``res.users._pk_extra_roles()``.
* UC-K2 A role declared with no group (« reserved ») resolves to nothing.
* UC-K3 ``portal.kit.pk_app_roles()`` is every declared role except those
  flagged ``'app': False`` (a backend-only role does not put a user in the
  app).
* UC-K4 The role registry is per-database code, cached per registry: two
  users of the same database get their own role set from the same cached
  registry (nothing per-user is cached); ``_pk_extra_roles`` is asked on
  every call.
* UC-K5 A consumer extends the hook with ``super()``: its roles are added to
  what is already declared.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged

from .common import pk_extra_roles, pk_hook

ROLES = {
    'kit_staff': {'groups': ('base.group_user',)},
    'kit_member': {'groups': ('base.group_portal',)},
    'kit_backend': {'groups': ('base.group_user',), 'app': False},
    'kit_reserved': {'groups': ()},
    'kit_extra': {'groups': ()},
}


@tagged('post_install', '-at_install')
class TestPkRoles(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def _user(login, xmlid):
            return cls.env['res.users'].with_context(no_reset_password=True).create({
                'name': login, 'login': '%s@example.com' % login,
                'group_ids': [Command.set([cls.env.ref(xmlid).id])],
            })

        cls.internal = _user('pk.internal', 'base.group_user')
        cls.member = _user('pk.member', 'base.group_portal')

    def _roles(self):
        return pk_hook(self.env, '_pk_roles', lambda _orig: ROLES)

    def _no_extra(self):
        return pk_extra_roles(self.env, lambda user: frozenset())

    # -- UC-K1 / UC-K2 ----------------------------------------------------
    def test_roles_from_groups(self):
        with self._roles(), self._no_extra():
            self.assertEqual(self.internal._pk_roles(), frozenset({'kit_staff', 'kit_backend'}))
            self.assertEqual(self.member._pk_roles(), frozenset({'kit_member'}))

    def test_extra_roles_are_united(self):
        def extra(user):
            return frozenset({'kit_extra'}) if user == self.member else frozenset()

        with self._roles(), pk_extra_roles(self.env, extra):
            self.assertEqual(self.member._pk_roles(), frozenset({'kit_member', 'kit_extra'}))
            self.assertNotIn('kit_extra', self.internal._pk_roles())

    def test_reserved_role_resolves_to_nothing(self):
        with self._roles(), self._no_extra():
            for user in (self.internal, self.member):
                self.assertNotIn('kit_reserved', user._pk_roles())

    def test_kit_alone_declares_no_extra_role(self):
        """The kit's own ``_pk_extra_roles`` is empty (consumers add theirs)."""
        base = type(self.env['res.users'])
        kit_impl = next(klass.__dict__['_pk_extra_roles'] for klass in base.__mro__
                        if getattr(klass, '_module', None) == 'bemade_portal_kit'
                        and '_pk_extra_roles' in klass.__dict__)
        self.assertEqual(kit_impl(self.member), frozenset())

    # -- UC-K3 ------------------------------------------------------------
    def test_app_roles_drop_backend_only_roles(self):
        with self._roles():
            app = self.env['portal.kit'].pk_app_roles()
        self.assertEqual(app, frozenset({'kit_staff', 'kit_member', 'kit_reserved', 'kit_extra'}))

    # -- UC-K4 ------------------------------------------------------------
    def test_registry_is_cached_but_not_per_user(self):
        calls = []

        def build(_orig):
            calls.append(1)
            return ROLES

        with pk_hook(self.env, '_pk_roles', build), self._no_extra():
            first = self.internal._pk_roles()
            second = self.member._pk_roles()
            self.internal._pk_roles()
            self.env['portal.kit'].pk_app_roles()
        self.assertEqual(len(calls), 1, 'the role registry is built once per registry')
        self.assertNotEqual(first, second)

    def test_extra_roles_are_never_cached(self):
        seen = []

        def extra(user):
            seen.append(user.id)
            return frozenset()

        with self._roles(), pk_extra_roles(self.env, extra):
            self.member._pk_roles()
            self.member._pk_roles()
        self.assertEqual(seen, [self.member.id, self.member.id])

    def test_registry_is_read_only(self):
        with self._roles():
            roles = self.env['portal.kit'].pk_roles()
            with self.assertRaises(TypeError):
                roles['kit_new'] = {'groups': ()}
            with self.assertRaises(TypeError):
                roles['kit_staff']['groups'] = ('base.group_system',)

    # -- UC-K5 ------------------------------------------------------------
    def test_consumer_extends_with_super(self):
        def extend(orig):
            return dict(orig, kit_more={'groups': ('base.group_portal',)})

        with self._roles(), pk_hook(self.env, '_pk_roles', extend), self._no_extra():
            self.assertEqual(self.member._pk_roles(), frozenset({'kit_member', 'kit_more'}))
