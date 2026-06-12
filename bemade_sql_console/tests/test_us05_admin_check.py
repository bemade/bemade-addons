"""
US-05 — Non-admin user calling run_query raises AccessError.

Acceptance criteria
-------------------
- A user with only base.group_user (not group_sql_console) calling
  env["sql.console"].with_user(non_admin).run_query("SELECT 1")
  raises odoo.exceptions.AccessError.
- The AccessError is raised BEFORE any SQL is validated or connection opened.
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.tools.misc import mute_logger

from .common import SqlConsoleTestBase


@tagged("at_install", "post_install")
class TestAdminCheck(SqlConsoleTestBase):
    """US-05: Non-members of group_sql_console are denied at the method boundary."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a plain portal/internal user without group_sql_console
        cls.non_admin_user = new_test_user(
            cls.env,
            login="sql_console_nobody",
            groups="base.group_user",
        )

    def test_non_admin_raises_access_error(self):
        """with_user(non_admin).run_query raises AccessError immediately."""
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises(AccessError):
                (
                    self.env["sql.console"]
                    .with_user(self.non_admin_user)
                    .run_query("SELECT 1")
                )

    def test_access_error_before_env_check(self):
        """AccessError fires even when env vars are unset (auth is first check)."""
        import os

        saved_user = os.environ.pop("ODOO_RO_DB_USER", None)
        saved_pass = os.environ.pop("ODOO_RO_DB_PASSWORD", None)
        try:
            with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
                with self.assertRaises(AccessError):
                    (
                        self.env["sql.console"]
                        .with_user(self.non_admin_user)
                        .run_query("SELECT 1")
                    )
        finally:
            if saved_user is not None:
                os.environ["ODOO_RO_DB_USER"] = saved_user
            if saved_pass is not None:
                os.environ["ODOO_RO_DB_PASSWORD"] = saved_pass

    def test_admin_user_is_allowed(self):
        """The test-running admin (env.user) is a member of group_sql_console.

        Because group_sql_console uses implied_by_ids = [base.group_system],
        all system admins inherit it.  This verifies that the module's group
        inheritance wiring is correct.
        """
        # self.env.user is admin in TransactionCase
        is_member = self.env.user.has_group(
            "bemade_sql_console.group_sql_console"
        )
        self.assertTrue(
            is_member,
            "Admin user should be a member of group_sql_console via implied_by_ids",
        )

    def test_non_admin_user_not_in_group(self):
        """The non-admin test user does not have group_sql_console."""
        is_member = self.non_admin_user.has_group(
            "bemade_sql_console.group_sql_console"
        )
        self.assertFalse(
            is_member,
            "Non-admin user should NOT be in group_sql_console",
        )
