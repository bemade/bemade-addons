"""
sql.console — read-only SQL console service model.

Security model
--------------
1. In-method group check (AccessError) — the only RPC trust boundary, because
   Odoo's RPC dispatcher does NOT rights-check method calls beyond authentication.
2. Role-level ACL — connection opens as ODOO_RO_DB_USER (SELECT-only role);
   writes rejected by PostgreSQL regardless of SQL content.
3. App-layer read-only — set_session(readonly=True) as defense-in-depth.
4. Single-statement guard — friendly error before any connection is opened.
5. Statement timeout — libpq options + SET belt-and-braces.
"""

import base64
import datetime
import decimal
import logging
import os
import re
import uuid

import psycopg2
import psycopg2.errors
import psycopg2.extensions as _psyext

import odoo.sql_db
from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

# ---------------------------------------------------------------------------
# Connection-scoped NUMERIC → Decimal type override
# ---------------------------------------------------------------------------
# Odoo globally registers a process-wide psycopg2 adapter that maps NUMERIC
# (OID 1700) to Python float (odoo/sql_db.py, DECIMAL_TO_FLOAT_TYPE).  That
# adapter fires on every connection in the process, including ours, and makes
# the decimal.Decimal branch in _jsonify unreachable.
#
# We counter this by registering a *connection-scoped* type override on the RO
# connection immediately after opening it.  psycopg2 resolves type casters in
# this order: connection-scoped → cursor-scoped → global.  Registering on the
# connection therefore shadows Odoo's global float adapter for our connection
# only, without touching the global registration or Odoo's pool.
#
# OID 1700 = numeric / decimal  (also used for numeric[])
# The caster is identical to psycopg2's built-in DECIMAL caster: convert the
# string representation to decimal.Decimal, or None for SQL NULL.
_NUMERIC_OID = 1700
_NUMERIC_ARRAY_OID = 1231  # numeric[]
_DEC2DEC_TYPE = _psyext.new_type(
    (_NUMERIC_OID,),
    "DECIMAL",
    lambda v, c: decimal.Decimal(v) if v is not None else None,
)
_DEC2DEC_ARRAY_TYPE = _psyext.new_array_type(
    (_NUMERIC_ARRAY_OID,),
    "DECIMAL[]",
    _DEC2DEC_TYPE,
)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# _jsonify — make psycopg2 native types JSON-serializable
# ---------------------------------------------------------------------------

def _jsonify(v):
    """Recursively coerce a psycopg2 value to a JSON-serializable Python object.

    Key decisions:
    - decimal.Decimal → str  (LOCKED: preserves exact values for Trial Balance;
      do NOT change to float — precision loss on monetary/numeric is unacceptable)
    - datetime/date/time → ISO-8601 string
    - timedelta → total_seconds() float
    - bytes/memoryview → base64 string
    - uuid.UUID → str
    - dict/list — recurse
    - None, bool, int, float, str — as-is
    - anything else — str() fallback
    """
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, decimal.Decimal):
        return str(v)
    if isinstance(v, datetime.datetime):
        return v.isoformat()
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, datetime.time):
        return v.isoformat()
    if isinstance(v, datetime.timedelta):
        return v.total_seconds()
    if isinstance(v, (bytes, memoryview)):
        raw = bytes(v)
        return base64.b64encode(raw).decode("ascii")
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, dict):
        return {k: _jsonify(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_jsonify(item) for item in v]
    # Fallback — never let a non-serializable type escape
    return str(v)


# ---------------------------------------------------------------------------
# Single-statement guard (belt check, NOT the security boundary)
# ---------------------------------------------------------------------------

# Regex to strip leading SQL line comments (-- …\n)
_LINE_COMMENT_RE = re.compile(r"--[^\n]*\n?")
# Regex to strip block comments (/* … */)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

# Leading verbs that are allowed (only SELECT and WITH for CTEs)
_ALLOWED_LEADING_VERBS = frozenset(["select", "with"])


def _validate_single_select(sql: str) -> None:
    """Raise UserError if *sql* is not a single SELECT/WITH statement.

    This is a *belt* check for user-friendliness and criterion 5 compliance —
    NOT the security boundary.  A writable CTE starting with WITH passes this
    guard and is then rejected by the RO role at execution time.

    Algorithm
    ---------
    1. Strip leading SQL comments and whitespace.
    2. Require the first keyword to be SELECT or WITH.
    3. Scan the remaining text for a semicolon that is not inside a quoted
       string or identifier literal (single-quotes, double-quotes,
       dollar-quoting, or comments).  A single trailing semicolon is allowed;
       anything beyond it (i.e. a second statement) is rejected.
    """
    if not sql or not sql.strip():
        raise UserError(_("Please enter a SQL query."))

    # Strip comments to find the leading verb
    stripped = _LINE_COMMENT_RE.sub(" ", sql)
    stripped = _BLOCK_COMMENT_RE.sub(" ", stripped)
    stripped = stripped.strip()

    # Identify first keyword
    first_word = re.match(r"[A-Za-z_]+", stripped)
    if not first_word or first_word.group(0).lower() not in _ALLOWED_LEADING_VERBS:
        verb = first_word.group(0) if first_word else "<empty>"
        raise UserError(
            _(
                "Only SELECT or WITH queries are allowed. "
                "Got leading keyword: %(verb)s",
                verb=verb.upper(),
            )
        )

    # State-machine scan for extra statement boundaries (semicolons outside literals)
    _scan_for_multiple_statements(sql)


def _scan_for_multiple_statements(sql: str) -> None:
    """Scan *sql* for semicolons outside of string/identifier literals.

    We allow at most one trailing semicolon (common habit).  A semicolon in
    any position other than the very end of the meaningful SQL (ignoring
    trailing whitespace/comments) is interpreted as a statement boundary →
    UserError.

    Handles:
    - Single-quoted strings  'it''s fine'
    - Double-quoted identifiers  "my table"
    - Dollar-quoted strings  $tag$body$tag$
    - Line comments  -- comment
    - Block comments  /* comment */
    """
    i = 0
    n = len(sql)
    semicolon_positions = []  # positions of unquoted semicolons

    while i < n:
        c = sql[i]

        # Line comment — skip to end of line
        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            while i < n and sql[i] != "\n":
                i += 1
            continue

        # Block comment — skip to */
        if c == "/" and i + 1 < n and sql[i + 1] == "*":
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2  # skip */
            continue

        # Single-quoted string — skip, handling '' escapes
        if c == "'":
            i += 1
            while i < n:
                if sql[i] == "'" and i + 1 < n and sql[i + 1] == "'":
                    i += 2  # escaped quote
                elif sql[i] == "'":
                    i += 1
                    break
                else:
                    i += 1
            continue

        # Double-quoted identifier — skip, handling "" escapes
        if c == '"':
            i += 1
            while i < n:
                if sql[i] == '"' and i + 1 < n and sql[i + 1] == '"':
                    i += 2
                elif sql[i] == '"':
                    i += 1
                    break
                else:
                    i += 1
            continue

        # Dollar-quoted string  $tag$...$tag$
        if c == "$":
            # Look for the closing $ of the tag
            j = i + 1
            while j < n and sql[j] != "$":
                j += 1
            if j < n:
                tag = sql[i : j + 1]  # e.g. "$tag$" or "$$"
                end = sql.find(tag, j + 1)
                if end != -1:
                    i = end + len(tag)
                    continue
            # Not a dollar-quote (lone $) — fall through
            i += 1
            continue

        # Semicolon outside any literal
        if c == ";":
            semicolon_positions.append(i)

        i += 1

    if not semicolon_positions:
        return  # no semicolons — fine

    # Allow exactly one trailing semicolon (nothing meaningful after it)
    if len(semicolon_positions) == 1:
        after = sql[semicolon_positions[0] + 1 :].strip()
        # Strip trailing comments too
        after = _LINE_COMMENT_RE.sub("", after).strip()
        after = _BLOCK_COMMENT_RE.sub("", after).strip()
        if not after:
            return  # trailing semicolon — acceptable

    raise UserError(
        _(
            "Only a single SQL statement is allowed. "
            "Multiple statements separated by semicolons are not permitted."
        )
    )


# ---------------------------------------------------------------------------
# sql.console service model
# ---------------------------------------------------------------------------


class SqlConsole(models.Model):
    """Thin service model exposing run_query over RPC.

    No stored fields — this model exists purely to carry the run_query method
    and its helpers so it is addressable by name over execute_kw.
    """

    _name = "sql.console"
    _description = "Read-only SQL Console"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @api.model
    def run_query(self, sql: str) -> dict:
        """Execute *sql* as the read-only Postgres role and return a JSON envelope.

        Parameters
        ----------
        sql:
            A single SELECT or WITH statement (WITH may include non-writable CTEs).

        Returns
        -------
        dict with keys:
            columns   — list of column name strings
            rows      — list of lists (each value JSON-serializable)
            row_count — int, number of rows returned (≤ row_cap)
            truncated — bool, True when more rows exist beyond the cap

        Raises
        ------
        AccessError  — caller is not in group_sql_console
        UserError    — env vars absent, guard violation, or timeout
        """
        # 1. Authorization — MUST be first; this is the only RPC trust boundary
        if not self.env.user.has_group("bemade_sql_console.group_sql_console"):
            raise AccessError(_("You are not allowed to run SQL console queries."))

        # 2. Validate the SQL text before touching any connection
        _validate_single_select(sql)

        # 3. Resolve RO credentials — fail fast if not configured
        ro_user = os.environ.get("ODOO_RO_DB_USER", "").strip()
        ro_password = os.environ.get("ODOO_RO_DB_PASSWORD", "").strip()
        if not ro_user or not ro_password:
            raise UserError(
                _(
                    "The read-only SQL console is not configured on this instance. "
                    "Please contact your system administrator."
                )
            )

        # 4. Read runtime parameters
        get_param = self.env["ir.config_parameter"].sudo().get_param
        try:
            row_cap = int(get_param("bemade_sql_console.row_cap", "1000"))
        except (ValueError, TypeError):
            row_cap = 1000
        try:
            timeout_ms = int(
                get_param("bemade_sql_console.statement_timeout_ms", "30000")
            )
        except (ValueError, TypeError):
            timeout_ms = 30000

        # 5. Build connection info (host/port/sslmode from Odoo config; replica-aware)
        conn_info = self._ro_connection_info(ro_user, ro_password, timeout_ms)

        # 6. Open RO connection and execute
        conn = None
        try:
            conn = psycopg2.connect(**conn_info)
            # Override Odoo's global NUMERIC→float adapter with a
            # connection-scoped NUMERIC→Decimal caster so _jsonify's
            # decimal.Decimal → str branch works as specified.
            # This does NOT affect Odoo's process-global adapter or its pool.
            _psyext.register_type(_DEC2DEC_TYPE, conn)
            _psyext.register_type(_DEC2DEC_ARRAY_TYPE, conn)
            # App-layer read-only (defense-in-depth — in addition to role ACL)
            conn.set_session(readonly=True, autocommit=False)

            with conn:
                with conn.cursor() as cur:
                    # Belt-and-braces: also SET via SQL (catches proxies that strip
                    # libpq options) — this is inside the RO transaction
                    cur.execute(f"SET statement_timeout = {int(timeout_ms)}")
                    cur.execute(sql)
                    columns = (
                        [d.name for d in cur.description]
                        if cur.description
                        else []
                    )
                    rows = cur.fetchmany(row_cap + 1)  # +1 to detect truncation
                    truncated = len(rows) > row_cap
                    rows = rows[:row_cap]

            return {
                "columns": columns,
                "rows": [[_jsonify(v) for v in row] for row in rows],
                "row_count": len(rows),
                "truncated": truncated,
            }

        except psycopg2.errors.QueryCanceled:
            raise UserError(
                _(
                    "Query exceeded the time limit (%(ms)d ms) and was cancelled.",
                    ms=timeout_ms,
                )
            )
        except psycopg2.Error as exc:
            _logger.debug("SQL console query failed: %s", exc)
            raise UserError(
                _("Query failed: %(error)s", error=str(exc).strip())
            )
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ro_connection_info(
        self, ro_user: str, ro_password: str, timeout_ms: int
    ) -> dict:
        """Return psycopg2 connect kwargs for the read-only role.

        Strategy
        --------
        1. Derive host/port/sslmode from Odoo's own config (replica-aware) via
           ``odoo.sql_db.connection_info_for(dbname, readonly=True)``.
        2. Override user/password with the RO credentials from env.
        3. Set statement_timeout via libpq ``options`` so it applies before the
           first statement (belt 1; belt 2 is the SET inside run_query).
        """
        dbname = self.env.cr.dbname
        _dbname, info = odoo.sql_db.connection_info_for(dbname, readonly=True)
        # Override credentials — discard whatever owner user/password was filled in
        info["user"] = ro_user
        info["password"] = ro_password
        # libpq options for statement_timeout (connection-level GUC)
        info["options"] = f"-c statement_timeout={int(timeout_ms)}"
        return info
