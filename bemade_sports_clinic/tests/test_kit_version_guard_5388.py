# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5388: the clinic's upgrade checks the kit's version before any of
its pre-migrations moves kit data.

Acceptance criteria:

* UC-C1 The check is a ``0.0.0`` pre-migration: Odoo runs it first among
  the pre-migrations of every upgrade, before the versioned ones (which
  adopt views and move columns into the kit).
* UC-C2 On a database whose kit is older than ``PK_MIN_VERSION`` it raises
  ``PkKitVersionError``, naming this addon; on a new enough kit it is a
  no-op.
* UC-C3 The check is the script's first statement.
"""
import ast
import importlib.util
import os

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tools.version_guard import PkKitVersionError

SCRIPT = os.path.join(
    get_module_path('bemade_sports_clinic'), 'migrations', '0.0.0', 'pre-kit-version-guard.py')


def load_script():
    spec = importlib.util.spec_from_file_location('sc_pre_kit_version_guard_5388', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged('post_install', '-at_install')
class TestKitVersionGuard5388(TransactionCase):

    def _set_kit(self, version):
        self.env.cr.execute(
            "UPDATE ir_module_module SET latest_version = %s WHERE name = 'bemade_portal_kit'", (version,))

    # UC-C1
    def test_runs_first_on_every_upgrade(self):
        self.assertTrue(os.path.isfile(SCRIPT), SCRIPT)

    # UC-C2
    @mute_logger('odoo.addons.bemade_portal_kit.tools.version_guard')
    def test_old_kit_raises(self):
        self._set_kit('19.0.1.2.0')
        with self.assertRaises(PkKitVersionError) as ctx:
            load_script().migrate(self.env.cr, '19.0.1.136.0')
        self.assertIn('bemade_sports_clinic needs bemade_portal_kit >=', str(ctx.exception))

    def test_new_enough_kit_is_a_noop(self):
        self.assertIsNone(load_script().migrate(self.env.cr, '19.0.1.148.0'))

    # UC-C3
    def test_guard_is_the_first_statement(self):
        with open(SCRIPT) as f:
            tree = ast.parse(f.read())
        migrate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'migrate')
        body = [s for s in migrate.body
                if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
        call = body[0].value
        self.assertEqual(call.func.id if isinstance(call.func, ast.Name) else call.func.attr, 'require_kit')
