"""Shared test infrastructure for bemade_sql_console.

Phase 4 will implement the RO-role provisioning helpers here.
Skeleton only — do not instantiate directly.
"""

from odoo.tests.common import TransactionCase


class SqlConsoleTestBase(TransactionCase):
    """Base class for bemade_sql_console tests.

    Phase 4 will add:
    - setUpClass: CREATE ROLE <tmp_ro> with SELECT-only grants; sets
      ODOO_RO_DB_USER / ODOO_RO_DB_PASSWORD env vars.
    - tearDownClass: DROP OWNED BY / DROP ROLE <tmp_ro>; restores env.
    - _skip_if_no_createrole(): detect CREATEROLE availability and call
      self.skipTest with a clear message if absent, degrading gracefully.
    """
