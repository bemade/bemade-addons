# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""The multi-database leak, proved structurally.

Before the kit, the shell's registries were module-level dicts and a
consumer addon added its pages at import time (``PAGES.setdefault``): on a
server serving several databases, the pages leaked into every database,
including those where the addon is not installed.

A faithful two-database test cannot run inside one test database (a test
runs on one registry). The kit therefore proves the property structurally
here, and the build ran the two-registry check out of the suite (see the
task's dev-review artifact):

* UC-K22 Every class that contributes a ``_pk_*`` hook to this database's
  ``portal.kit`` belongs to a module INSTALLED in this database: the hook
  content is the registry's own class chain, nothing else.
* UC-K23 The kit's Python modules hold no mutable module-level container
  (dict / list / set) that a consumer could mutate at import time.
* UC-K24 The cached registries live in the database's registry cache: a
  cache clear rebuilds them from the hooks (the cache is per registry,
  never process-global).
"""
import inspect

from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit import tools as pk_tools
from odoo.addons.bemade_portal_kit.models import portal_kit as pk_model
from odoo.addons.bemade_portal_kit.models import res_users as pk_users
from odoo.addons.bemade_portal_kit.controllers import pk_app as pk_controller

from .common import pk_hook

HOOKS = ('_pk_roles', '_pk_nav', '_pk_visibility', '_pk_pages', '_pk_save_specs',
         '_pk_fragment_fillers', '_pk_activity_can_act', '_pk_activity_assignable_users')


@tagged('post_install', '-at_install')
class TestPkNoLeak(TransactionCase):

    def test_hook_contributors_are_installed_modules(self):
        installed = set(self.env['ir.module.module'].search(
            [('state', 'in', ('installed', 'to upgrade'))]).mapped('name'))
        contributors = set()
        for klass in type(self.env['portal.kit']).__mro__:
            module = klass.__dict__.get('_module')
            if module and any(hook in klass.__dict__ for hook in HOOKS):
                contributors.add(module)
        self.assertIn('bemade_portal_kit', contributors)
        self.assertFalse(contributors - installed, 'hooks from a module not installed here')

    def test_no_mutable_module_state(self):
        for module in (pk_tools, pk_model, pk_users, pk_controller) + tuple(
                obj for _name, obj in inspect.getmembers(pk_tools, inspect.ismodule)):
            for name, value in vars(module).items():
                if name.startswith('__'):
                    continue
                self.assertNotIsInstance(
                    value, (dict, list, set), '%s.%s is mutable module state' % (
                        module.__name__, name))

    def test_cache_is_per_registry_and_rebuilt(self):
        calls = []

        def build(orig):
            calls.append(1)
            return orig

        kit = self.env['portal.kit']
        with pk_hook(self.env, '_pk_pages', build):
            kit.pk_pages()
            kit.pk_pages()
            self.assertEqual(len(calls), 1)
            self.env.registry.clear_cache()
            kit.pk_pages()
            self.assertEqual(len(calls), 2)
