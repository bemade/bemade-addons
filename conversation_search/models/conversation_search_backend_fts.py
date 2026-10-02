#
#    Bemade Inc.
#
#    Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact: marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License,
#    version 3.
#
#    For full license details, see https://www.gnu.org/licenses/lgpl-3.0.en.html.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
import unicodedata

from odoo import api, models
from odoo.tools import SQL

INDEX_NAME = "conversation_search_mail_message_tsv_idx"
FUNC_FOLD = "conversation_search_fold"
FUNC_TSV = "conversation_search_tsv"

# Bump whenever the body of one of the SQL functions below changes: the
# functions are declared IMMUTABLE, so Postgres trusts the stored index
# entries; ``_fts_ensure_index`` REINDEXes when the stamp stored in the
# function COMMENT differs from this value.
FTS_VERSION = "conversation_search_fts_v1"


def _build_fold_maps():
    """Accented Latin letters (both cases) -> lower-case ASCII."""
    src, dst = [], []
    for cp in list(range(0xC0, 0x180)):
        char = chr(cp)
        if char in "ÆæŒœßÐðÞþ×÷":
            continue
        decomposed = unicodedata.normalize("NFD", char)
        base = decomposed[0]
        if len(decomposed) > 1 and base.isascii() and base.isalpha():
            src.append(char)
            dst.append(base.lower())
    for char, base in (
        ("Ø", "o"),
        ("ø", "o"),
        ("Đ", "d"),
        ("đ", "d"),
        ("Ł", "l"),
        ("ł", "l"),
        ("Ð", "d"),
        ("ð", "d"),
    ):
        src.append(char)
        dst.append(base)
    return "".join(src), "".join(dst)


_FOLD_FROM, _FOLD_TO = _build_fold_maps()

_FOLD_FUNCTION = f"""
CREATE OR REPLACE FUNCTION {{schema}}.{FUNC_FOLD}(txt text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $fn$
    SELECT translate(
        replace(replace(replace(replace(replace(replace(coalesce(txt, ''),
            'œ', 'oe'), 'Œ', 'oe'), 'æ', 'ae'), 'Æ', 'ae'), 'ß', 'ss'),
            'þ', 'th'),
        '{_FOLD_FROM}',
        '{_FOLD_TO}'
    )
$fn$
"""

# Strip markup so tag / attribute names never reach the tsvector.
_STRIP = (
    "regexp_replace("
    "regexp_replace("
    "regexp_replace("
    "regexp_replace("
    "regexp_replace("
    "regexp_replace(left(coalesce(body, ''), 500000),"
    " '<!--.*?-->', ' ', 'g'),"
    " '<style\\M.*?</style>', ' ', 'gi'),"
    " '<script\\M.*?</script>', ' ', 'gi'),"
    " '<[^>]*>', ' ', 'g'),"
    " '&amp;', '&', 'g'),"
    " '&[#a-zA-Z0-9]+;', ' ', 'g')"
)

_TSV_FUNCTION = f"""
CREATE OR REPLACE FUNCTION {{schema}}.{FUNC_TSV}(subject text, body text) RETURNS tsvector
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $fn$
    SELECT setweight(to_tsvector('simple'::regconfig,
               {{schema}}.{FUNC_FOLD}(left(coalesce(subject, ''), 2000))), 'A')
        || setweight(to_tsvector('simple'::regconfig,
               {{schema}}.{FUNC_FOLD}(left({_STRIP}, 200000))), 'D')
$fn$
"""


def fts_drop_objects(cr):
    cr.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
    cr.execute(f"DROP FUNCTION IF EXISTS {FUNC_TSV}(text, text)")
    cr.execute(f"DROP FUNCTION IF EXISTS {FUNC_FOLD}(text)")


class ConversationSearchBackendFts(models.AbstractModel):
    """PostgreSQL full-text backend (``fts``).

    A pure DB-level partial GIN expression index on ``mail_message``
    restricted to ``model = 'mail.conversation'``. Postgres maintains it in
    the same statement as every insert / update / delete, so there is no
    ORM override, no trigger, no extra column and no cron.

    Text-search configuration is ``simple`` (no stop words, no stemming):
    mixed French / English mail loses no words; the trade-off is that
    "pompes" does not match "pompe" (type ``pompe OR pompes``). Accents are
    folded by :data:`FUNC_FOLD` without the ``unaccent`` extension.

    Note: a query consisting only of negations (``-pompe``) matches every
    conversation having at least one message lacking the word; GIN answers
    it by scanning the whole index, which is correct but slow.
    """

    _inherit = "conversation.search.backend"

    # ------------------------------------------------------------------
    # Index lifecycle
    # ------------------------------------------------------------------
    def init(self):
        super().init()
        self._fts_ensure_index()

    @api.model
    def _fts_ensure_index(self):
        cr = self.env.cr
        # Read the OLD stamp before overwriting it.
        cr.execute(
            "SELECT obj_description(p.oid, 'pg_proc') FROM pg_proc p "
            "WHERE p.proname = %s AND p.pronargs = 2",
            [FUNC_TSV],
        )
        row = cr.fetchone()
        old_stamp = row[0] if row else None
        # Index expressions are evaluated under a restricted search_path
        # (PG 17+ maintenance operations), so the function bodies must
        # schema-qualify the helper they call.
        cr.execute("SELECT current_schema()")
        schema = cr.fetchone()[0]
        cr.execute(_FOLD_FUNCTION.replace("{schema}", schema))
        cr.execute(_TSV_FUNCTION.replace("{schema}", schema))
        cr.execute(f"COMMENT ON FUNCTION {FUNC_TSV}(text, text) IS %s", [FTS_VERSION])
        cr.execute("SELECT to_regclass(%s)", [INDEX_NAME])
        index_exists = cr.fetchone()[0] is not None
        cr.execute(
            f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON mail_message "
            f"USING gin ({FUNC_TSV}(subject, body)) "
            f"WHERE model = 'mail.conversation'"
        )
        if index_exists and old_stamp != FTS_VERSION:
            cr.execute(f"REINDEX INDEX {INDEX_NAME}")

    # ------------------------------------------------------------------
    # SQL helpers
    # ------------------------------------------------------------------
    @api.model
    def _fts_flush(self):
        self.env["mail.message"].flush_model(["body", "subject", "model", "res_id"])

    @api.model
    def _fts_tsquery(self, text):
        return SQL(
            "websearch_to_tsquery('simple'::regconfig, %s(%s))",
            SQL.identifier(FUNC_FOLD),
            text,
        )

    @api.model
    def _fts_tsv(self, alias="m"):
        return SQL(
            "%s(%s, %s)",
            SQL.identifier(FUNC_TSV),
            SQL.identifier(alias, "subject"),
            SQL.identifier(alias, "body"),
        )

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------
    @api.model
    def _search_domain_fts(self, text):
        self._fts_flush()
        subselect = SQL(
            "(SELECT m.res_id FROM mail_message m "
            "WHERE m.model = 'mail.conversation' AND %s @@ %s)",
            self._fts_tsv(),
            self._fts_tsquery(text),
        )
        return [("id", "any!", subselect)]

    @api.model
    def _fts_ranked_sql(self, text, domain=None, limit=80, offset=0):
        conv_query = self.env["mail.conversation"]._search(domain or [])
        tsv = self._fts_tsv()
        tsq = self._fts_tsquery(text)
        query = SQL(
            """
            SELECT m.res_id,
                   max(ts_rank_cd(%(tsv)s, %(tsq)s)) AS rank,
                   max(m.date) AS last_match_date,
                   array_agg(m.id ORDER BY m.date DESC, m.id DESC)
              FROM mail_message m
             WHERE m.model = 'mail.conversation'
               AND %(tsv)s @@ %(tsq)s
               AND m.res_id IN %(convs)s
             GROUP BY m.res_id
             ORDER BY rank DESC, last_match_date DESC NULLS LAST, m.res_id DESC
             LIMIT %(limit)s OFFSET %(offset)s
            """,
            tsv=tsv,
            tsq=tsq,
            convs=conv_query.subselect(),
            limit=limit,
            offset=offset or 0,
        )
        return query

    @api.model
    def _search_ranked_fts(self, text, domain=None, limit=80, offset=0):
        self._fts_flush()
        query = self._fts_ranked_sql(text, domain, limit, offset)
        self.env.cr.execute(query)
        rows = self.env.cr.fetchall()
        # Filter message ids through the ORM as the current user, so any
        # future note-level restriction carries through.
        all_ids = [mid for row in rows for mid in row[3]]
        readable = set(self.env["mail.message"].search([("id", "in", all_ids)]).ids)
        return [
            {
                "conversation_id": res_id,
                "rank": float(rank),
                "last_match_date": last_date,
                "message_ids": [mid for mid in message_ids if mid in readable],
            }
            for res_id, rank, last_date, message_ids in rows
        ]

    @api.model
    def _index_messages_fts(self, messages):
        """No-op: the GIN expression index is maintained by Postgres in the
        same statement as every write on ``mail_message``."""
        return True

    @api.model
    def _rebuild_index_fts(self):
        self._fts_ensure_index()
        self.env.cr.execute(f"REINDEX INDEX {INDEX_NAME}")
        return True
