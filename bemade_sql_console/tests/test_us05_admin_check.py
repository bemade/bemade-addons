"""
US-05 — Non-admin user calling run_query raises AccessError.

Acceptance criteria
-------------------
- A user with only base.group_user (not group_sql_console) calling
  env["sql.console"].with_user(non_admin).run_query("SELECT 1")
  raises odoo.exceptions.AccessError.

Phase 4: implement test body using new_test_user(env, login="nobody",
groups="base.group_user").
"""

from .common import SqlConsoleTestBase


class TestAdminCheck(SqlConsoleTestBase):
    """Phase 4 implements the test body."""
