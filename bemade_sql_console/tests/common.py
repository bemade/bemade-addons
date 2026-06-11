"""Shared test infrastructure for bemade_sql_console.

Provides SqlConsoleTestBase, which:
- Creates a throwaway SELECT-only Postgres role in setUpClass using self.env.cr
  (owner/superuser on the test DB) and sets ODOO_RO_DB_USER / ODOO_RO_DB_PASSWORD
  env vars so run_query opens a real connection as that role.
- Tears down the role and restores env vars in tearDownClass.
- Degrades gracefully (self.skipTest) when CREATEROLE is unavailable, to avoid
  false CI failures on constrained runners.
"""

import os
import secrets
import string

import psycopg2

from odoo.tests.common import TransactionCase

# Characters safe for a Postgres role name (letters/digits/underscore)
_ROLE_CHARS = string.ascii_lowercase + string.digits


def _random_suffix(n=8):
    return "".join(secrets.choice(_ROLE_CHARS) for _ in range(n))


class SqlConsoleTestBase(TransactionCase):
    """Base class for bemade_sql_console tests.

    setUpClass provisions a live SELECT-only Postgres role and injects
    ODOO_RO_DB_USER / ODOO_RO_DB_PASSWORD.  tearDownClass drops the role and
    restores env.

    If the test-runner's Postgres user lacks the privilege to CREATE ROLE, the
    entire class is skipped with a clear message — this is a CI-environment
    limitation, not an implementation defect.

    The env vars are set at the *class* level so all test methods within a
    subclass share the same RO role.  Individual tests that need to temporarily
    override the env vars must save/restore them themselves.
    """

    # Will be populated by setUpClass if role creation succeeds
    _ro_role_name: str = ""
    _ro_role_password: str = ""
    _saved_env: dict = {}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._saved_env = {
            "ODOO_RO_DB_USER": os.environ.get("ODOO_RO_DB_USER"),
            "ODOO_RO_DB_PASSWORD": os.environ.get("ODOO_RO_DB_PASSWORD"),
        }
        cls._ro_role_name = f"test_ro_{_random_suffix()}"
        cls._ro_role_password = secrets.token_urlsafe(16)

        dbname = cls.env.cr.dbname
        cr = cls.env.cr

        # Attempt to create the throwaway SELECT-only role.
        # On constrained CI runners (no CREATEROLE), we skip rather than fail.
        try:
            # Use autocommit-style via savepoint so we can catch the error
            # without rolling back the whole TransactionCase outer transaction.
            cr.execute("SAVEPOINT create_ro_role")
            cr.execute(
                f"CREATE ROLE {cls._ro_role_name} LOGIN PASSWORD %s",
                (cls._ro_role_password,),
            )
            cr.execute(
                f"GRANT CONNECT ON DATABASE {dbname} TO {cls._ro_role_name}"
            )
            cr.execute(
                f"GRANT USAGE ON SCHEMA public TO {cls._ro_role_name}"
            )
            cr.execute(
                f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {cls._ro_role_name}"
            )
            # Set default_transaction_read_only as an extra layer of defense
            cr.execute(
                f"ALTER ROLE {cls._ro_role_name} SET default_transaction_read_only = on"
            )
            cr.execute("RELEASE SAVEPOINT create_ro_role")
        except Exception as exc:
            cr.execute("ROLLBACK TO SAVEPOINT create_ro_role")
            cr.execute("RELEASE SAVEPOINT create_ro_role")
            cls.skipTest(
                f"Cannot create SELECT-only Postgres role (CREATEROLE missing?): {exc}. "
                "ACL-level write rejection (criterion 3) cannot be verified; "
                "only app-layer read-only (criterion 4) would be tested."
            )

        # Inject env vars so run_query opens a connection as the RO role
        os.environ["ODOO_RO_DB_USER"] = cls._ro_role_name
        os.environ["ODOO_RO_DB_PASSWORD"] = cls._ro_role_password

    @classmethod
    def tearDownClass(cls):
        cr = cls.env.cr
        if cls._ro_role_name:
            try:
                cr.execute("SAVEPOINT drop_ro_role")
                cr.execute(f"DROP OWNED BY {cls._ro_role_name}")
                cr.execute(f"DROP ROLE IF EXISTS {cls._ro_role_name}")
                cr.execute("RELEASE SAVEPOINT drop_ro_role")
            except Exception:
                cr.execute("ROLLBACK TO SAVEPOINT drop_ro_role")
                cr.execute("RELEASE SAVEPOINT drop_ro_role")

        # Restore env vars
        for key, val in cls._saved_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

        super().tearDownClass()

    def _get_ro_pid(self):
        """Return the backend PID of a fresh RO connection (for US-02 test)."""
        import psycopg2 as _psycopg2
        from odoo.models import Model as _OdooModel
        import odoo.sql_db as _sql_db

        dbname = self.env.cr.dbname
        _dbname, info = _sql_db.connection_info_for(dbname, readonly=True)
        info["user"] = os.environ["ODOO_RO_DB_USER"]
        info["password"] = os.environ["ODOO_RO_DB_PASSWORD"]
        conn = _psycopg2.connect(**info)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_backend_pid()")
                return cur.fetchone()[0]
        finally:
            conn.close()
