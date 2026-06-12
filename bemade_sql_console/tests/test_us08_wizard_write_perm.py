"""
US-08 — Wizard write-perm regression (ACL fix).

Acceptance criteria
-------------------
- A non-admin user who IS a member of bemade_sql_console.group_sql_console can
  with_user(member).create(...) a sql.console.wizard record and call
  action_run_query() WITHOUT an AccessError.
- The outcome is written: either a result envelope (result_json) on success, or
  an error_message on failure — but never an unhandled AccessError from the
  wizard's own write() on the transient model.

This is the regression test for the ir.model.access.csv write-perm fix that
grants perm_write on sql.console.wizard to group_sql_console members (so the
wizard can stash results into its own transient record).
"""

from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import SqlConsoleTestBase


@tagged("at_install", "post_install")
class TestWizardWritePerm(SqlConsoleTestBase):
    """US-08: group_sql_console member can run the wizard without AccessError."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A non-admin user who IS granted console access directly (not via
        # base.group_system) — the exact persona the ACL fix targets.
        cls.console_member = new_test_user(
            cls.env,
            login="sql_console_member",
            groups="base.group_user,bemade_sql_console.group_sql_console",
        )

    def test_member_can_run_wizard(self):
        """Member creates + runs the wizard without an AccessError."""
        self.assertTrue(
            self.console_member.has_group("bemade_sql_console.group_sql_console"),
            "Test user must be in group_sql_console for this regression to be meaningful",
        )

        wizard = (
            self.env["sql.console.wizard"]
            .with_user(self.console_member)
            .create({"sql_text": "SELECT 1 AS a"})
        )
        # Must not raise AccessError (the regression). The wizard catches query
        # errors internally and writes them to error_message.
        wizard.action_run_query()

        # The outcome must be written to the record: a result OR an error.
        self.assertTrue(
            wizard.result_json or wizard.error_message,
            "action_run_query must persist either a result or an error_message",
        )

    def test_member_run_writes_result_envelope(self):
        """On a successful SELECT, result_json carries the envelope."""
        wizard = (
            self.env["sql.console.wizard"]
            .with_user(self.console_member)
            .create({"sql_text": "SELECT 42 AS answer"})
        )
        wizard.action_run_query()

        self.assertFalse(
            wizard.error_message,
            "A valid SELECT should not produce an error_message: %s"
            % wizard.error_message,
        )
        self.assertTrue(wizard.result_json, "result_json should be populated")
        self.assertEqual(wizard.result_json.get("columns"), ["answer"])
        self.assertEqual(wizard.result_json.get("rows"), [[42]])
        self.assertEqual(wizard.row_count, 1)
