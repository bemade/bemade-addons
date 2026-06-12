{
    "name": "Read-only SQL Console",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "summary": "Admin-only read-only SQL console executed as a SELECT-only Postgres role",
    "description": """
Read-only SQL Console
=====================

Provides an admin-only ``run_query(sql)`` method (and matching CodeEditor view)
that executes a single SELECT statement as a SELECT-only PostgreSQL role over
its own dedicated connection — never the Odoo owner connection.

Key guarantees
--------------

* **Role-level write boundary.** The addon opens a fresh psycopg2 connection
  authenticated as the ``ODOO_RO_DB_USER`` role, which must be provisioned as a
  SELECT-only role by the ops team (odoo-operator PR #135). Writes are rejected
  at the PostgreSQL privilege layer regardless of SQL content.

* **Defense-in-depth.** The connection is additionally set read-only at the
  app layer (``set_session(readonly=True)``) so that even a misconfigured role
  is constrained.

* **Single-statement guard.** Only a single ``SELECT`` or ``WITH`` statement
  is accepted. Multiple statements or non-SELECT leading verbs are rejected
  immediately with a friendly error — before any connection is opened.

* **Statement timeout.** A configurable ``statement_timeout`` (default 30 s)
  is applied both via libpq ``options`` and as a first-cursor ``SET`` so that
  long-running queries are aborted server-side.

* **Row cap.** A configurable row cap (default 1000) bounds the rows returned
  to the on-screen UI table; the response envelope carries a ``truncated`` flag.

* **Streaming CSV export.** The "Download CSV" button streams the *full*
  result — no row cap, bounded only by ``statement_timeout`` — from a psycopg2
  server-side cursor through a dedicated HTTP controller
  (``/bemade_sql_console/export/<wizard_id>``). Rows are fetched and flushed in
  batches so arbitrarily large results never load fully into memory. The route
  re-enforces the ``group_sql_console`` check (403 otherwise) as the export
  trust boundary.

* **Graceful degradation.** When ``ODOO_RO_DB_USER``/``ODOO_RO_DB_PASSWORD``
  are not set (dev/test), ``run_query`` raises a clear "not configured" error
  rather than falling back to the owner connection.

* **RPC-callable.** ``run_query`` is an ``@api.model`` method callable over
  ``execute_kw`` by a user authenticated with an Odoo API key, making it
  suitable for BI tools and AI agents.

Security note
-------------

The statement-level guard (SELECT/WITH prefix check) is **not** the security
boundary — a writable CTE starting with ``WITH`` passes the guard and is then
rejected by the role ACL. The guard's job is user-friendliness (criterion 5),
not write prevention. The SELECT-only PostgreSQL role is the real boundary.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "views/sql_console_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bemade_sql_console/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
