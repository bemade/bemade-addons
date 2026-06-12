"""Shared test infrastructure for bemade_sql_console.

Provides SqlConsoleTestBase, which:
- Creates a throwaway SELECT-only Postgres role via a SEPARATE autocommit admin
  connection in setUpClass so the role is committed and visible to the
  independent psycopg2 connection opened by run_query.
- Tears down the role and restores env vars in tearDownClass via the same
  separate connection.
- Degrades gracefully (unittest.SkipTest) when CREATEROLE is unavailable, to
  avoid false CI failures on constrained runners.
"""

import os
import secrets
import string
import unittest

import psycopg2
import psycopg2.errors

import odoo.sql_db
from odoo.tests.common import TransactionCase

# Characters safe for a Postgres role name (letters/digits/underscore)
_ROLE_CHARS = string.ascii_lowercase + string.digits


def _random_suffix(n=8):
    return "".join(secrets.choice(_ROLE_CHARS) for _ in range(n))


def _admin_autocommit_conn(dbname):
    """Open a fresh psycopg2 connection to *dbname* with autocommit=True.

    Strategy: try the Odoo DB user first (same creds as odoo.sql_db). If that
    user lacks CREATEROLE, fall back to a local peer-auth connection as the OS
    user (for developer workstations where the OS user is a Postgres superuser).

    autocommit=True is mandatory: CREATE/DROP ROLE are DDL statements on the
    global role catalog; they must be committed immediately so the new role is
    visible to the independent psycopg2 connection opened by run_query.
    """
    _dbname, info = odoo.sql_db.connection_info_for(dbname)
    # First try: Odoo owner user (may or may not have CREATEROLE)
    try:
        conn = psycopg2.connect(**info)
        conn.autocommit = True
        # Quick privilege check — avoids misleading errors later
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rolcreaterole OR rolsuper FROM pg_roles WHERE rolname = current_user"
            )
            has_createrole = cur.fetchone()
            if has_createrole and has_createrole[0]:
                return conn
        conn.close()
    except Exception:
        pass

    # Second try: local peer-auth as the OS user (dev workstation, no password)
    local_user = os.environ.get("USER", "")
    if local_user:
        try:
            peer_info = {"database": dbname, "user": local_user}
            conn = psycopg2.connect(**peer_info)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT rolcreaterole OR rolsuper FROM pg_roles WHERE rolname = current_user"
                )
                has_createrole = cur.fetchone()
                if has_createrole and has_createrole[0]:
                    return conn
            conn.close()
        except Exception:
            pass

    return None


class SqlConsoleTestBase(TransactionCase):
    """Base class for bemade_sql_console tests.

    setUpClass provisions a live SELECT-only Postgres role via a SEPARATE
    autocommit admin connection and injects ODOO_RO_DB_USER /
    ODOO_RO_DB_PASSWORD.  tearDownClass drops the role and restores env.

    Using a separate autocommit connection is critical: run_query opens its
    own psycopg2 connection which cannot see roles created (but not committed)
    inside the TransactionCase outer transaction.  By committing via autocommit
    the role is immediately visible to all subsequent connections.

    If no connection with CREATEROLE/SUPERUSER privilege is available, the
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
    _admin_dbname: str = ""  # dbname used for teardown (peer conn needs it)

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
        cls._admin_dbname = dbname

        # Attempt to create the throwaway SELECT-only role via a SEPARATE
        # autocommit connection so the role is committed and visible to
        # run_query's independent psycopg2 connection.
        admin_conn = _admin_autocommit_conn(dbname)
        if admin_conn is None:
            raise unittest.SkipTest(
                "No Postgres connection with CREATEROLE/SUPERUSER privilege available. "
                "ACL-level write rejection (criterion 3) cannot be verified. "
                "Grant CREATEROLE to the Odoo DB user or run as a superuser OS user."
            )

        try:
            cur = admin_conn.cursor()
            cur.execute(
                f"CREATE ROLE {cls._ro_role_name} LOGIN PASSWORD %s",
                (cls._ro_role_password,),
            )
            cur.execute(
                f"GRANT CONNECT ON DATABASE {dbname} TO {cls._ro_role_name}"
            )
            cur.execute(
                f"GRANT USAGE ON SCHEMA public TO {cls._ro_role_name}"
            )
            cur.execute(
                f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {cls._ro_role_name}"
            )
            # Default RO transaction as extra defense layer
            cur.execute(
                f"ALTER ROLE {cls._ro_role_name} SET default_transaction_read_only = on"
            )
            cur.close()
        except Exception as exc:
            raise unittest.SkipTest(
                f"Cannot create SELECT-only Postgres role: {exc}. "
                "ACL-level write rejection (criterion 3) cannot be verified."
            )
        finally:
            try:
                admin_conn.close()
            except Exception:
                pass

        # Inject env vars so run_query opens a connection as the RO role
        os.environ["ODOO_RO_DB_USER"] = cls._ro_role_name
        os.environ["ODOO_RO_DB_PASSWORD"] = cls._ro_role_password

    @classmethod
    def tearDownClass(cls):
        if cls._ro_role_name:
            dbname = cls._admin_dbname or cls.env.cr.dbname
            admin_conn = _admin_autocommit_conn(dbname)
            if admin_conn is not None:
                try:
                    cur = admin_conn.cursor()
                    cur.execute(f"DROP OWNED BY {cls._ro_role_name}")
                    cur.execute(f"DROP ROLE IF EXISTS {cls._ro_role_name}")
                    cur.close()
                except Exception:
                    pass
                finally:
                    try:
                        admin_conn.close()
                    except Exception:
                        pass

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
