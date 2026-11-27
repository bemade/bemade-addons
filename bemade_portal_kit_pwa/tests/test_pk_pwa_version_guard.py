# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5388: this addon's install hook checks the kit's version first.

Acceptance criteria:

* UC-G1 On a database whose kit is older than ``PK_MIN_VERSION``, the
  install hook raises ``PkKitVersionError`` before it adopts or moves
  anything (the adoption is never called, nothing is written).
* UC-G2 The kit's version check is the hook's first statement.
* UC-G3 On a database whose kit is new enough, the hook runs as before.
"""
import ast
import inspect
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tools.version_guard import PkKitVersionError
from odoo.addons.bemade_portal_kit_pwa import hooks


def first_call_name(func):
    body = ast.parse(inspect.getsource(func)).body[0].body
    stmt = body[0]
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        stmt = body[1]  # a docstring
    call = stmt.value
    return call.func.id if isinstance(call.func, ast.Name) else call.func.attr


@tagged('post_install', '-at_install')
class TestPkPwaVersionGuard(TransactionCase):

    def _set_kit(self, version):
        self.env.cr.execute(
            "UPDATE ir_module_module SET latest_version = %s WHERE name = 'bemade_portal_kit'", (version,))

    def _snapshot(self):
        self.env.flush_all()
        self.env.cr.execute("SELECT count(*), max(write_date) FROM ir_model_data")
        data = self.env.cr.fetchone()
        self.env.cr.execute("SELECT count(*), max(write_date) FROM ir_ui_view")
        return data, self.env.cr.fetchone()

    # UC-G1
    @mute_logger('odoo.addons.bemade_portal_kit.tools.version_guard')
    def test_old_kit_stops_before_any_write(self):
        self._set_kit('19.0.1.2.0')
        before = self._snapshot()
        with patch.object(hooks, 'adopt_views') as adopt, self.assertRaises(PkKitVersionError) as ctx:
            hooks.pre_init_hook(self.env)
        adopt.assert_not_called()
        self.assertIn('bemade_portal_kit_pwa needs bemade_portal_kit >=', str(ctx.exception))
        self.assertEqual(self._snapshot(), before)

    # UC-G2
    def test_guard_is_the_first_statement(self):
        self.assertEqual(first_call_name(hooks.pre_init_hook), 'require_kit')

    # UC-G3
    def test_new_enough_kit_runs_the_hook(self):
        with patch.object(hooks, 'adopt_views') as adopt:
            hooks.pre_init_hook(self.env)
        adopt.assert_called_once()

    # Task 5546: the upgrade to 1.2 checks the kit (1.18) first.
    @mute_logger('odoo.addons.bemade_portal_kit.tools.version_guard')
    def test_upgrade_checks_the_kit(self):
        import importlib.util
        import os
        from odoo.modules.module import get_module_path
        path = os.path.join(get_module_path('bemade_portal_kit_pwa'), 'migrations', '19.0.1.2.0', 'pre-migrate.py')
        spec = importlib.util.spec_from_file_location('pk_pwa_pre_migrate_1_2', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.assertEqual(first_call_name(migration.migrate), 'require_kit')
        self._set_kit('19.0.1.17.0')
        with self.assertRaises(PkKitVersionError):
            migration.migrate(self.env.cr, '19.0.1.1.2')
        self._set_kit('19.0.1.18.0')
        self.assertIsNone(migration.migrate(self.env.cr, '19.0.1.1.2'))
