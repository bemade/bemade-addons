# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: this addon's install hook checks the kit's version first.

Acceptance criteria:

* UC-G1 On a database whose kit is older than 1.17.0, the install hook
  raises ``PkKitVersionError`` before anything is written.
* UC-G2 The kit's version check is the hook's first statement.
* UC-G3 On a database whose kit is new enough, the hook runs.
"""
import ast
import inspect

from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tools.version_guard import PK_MIN_VERSION, PkKitVersionError
from odoo.addons.bemade_portal_kit_chat import hooks


def first_call_name(func):
    body = ast.parse(inspect.getsource(func)).body[0].body
    stmt = body[0]
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        stmt = body[1]  # a docstring
    call = stmt.value
    return call.func.id if isinstance(call.func, ast.Name) else call.func.attr


@tagged('post_install', '-at_install')
class TestPkChatVersionGuard(TransactionCase):

    def _set_kit(self, version):
        self.env.cr.execute(
            "UPDATE ir_module_module SET latest_version = %s WHERE name = 'bemade_portal_kit'", (version,))

    # UC-G1
    @mute_logger('odoo.addons.bemade_portal_kit.tools.version_guard')
    def test_old_kit_stops(self):
        self._set_kit('19.0.1.16.0')
        with self.assertRaises(PkKitVersionError) as ctx:
            hooks.pre_init_hook(self.env)
        self.assertIn('bemade_portal_kit_chat needs bemade_portal_kit >= 19.0.1.17.0', str(ctx.exception))

    # UC-G2
    def test_guard_is_the_first_statement(self):
        self.assertEqual(first_call_name(hooks.pre_init_hook), 'require_kit')
        self.assertEqual(hooks.CHAT_MIN_KIT, '19.0.1.17.0')
        self.assertEqual(PK_MIN_VERSION, '19.0.1.17.0')

    # UC-G3
    def test_new_enough_kit_runs(self):
        self._set_kit('19.0.1.17.0')
        self.assertIsNone(hooks.pre_init_hook(self.env))
