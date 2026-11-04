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
"""Index-usability and performance checks for the FTS GIN expression index.

Two groups with different guarantees:

* ``TestIndexPlan`` runs in the default test selection (``standard``). It
  proves the index *can* serve both search paths without asserting on the
  planner's cost-based choice or on wall-clock time, so the outcome does not
  depend on table statistics, on other addons' rows in ``mail_message`` or on
  runner load. Inside the test's own transaction it (1) drops every other
  non-constraint index on ``mail_message`` and (2) disables seq/index scans
  (``SET LOCAL``), leaving the GIN index as the only possible non-seq access
  path. Both changes are rolled back with the test savepoint, so nothing
  leaks into other tests of a shared database. The negative tests prove the
  check is not vacuous: it fails when the index is missing, when the query
  expression does not match the index expression, and when the partial index
  predicate is not implied by the query.

* ``TestIndexPerf`` keeps the original real-planner plan assertions and the
  < 1 s wall-clock checks on a 10,000-message fixture. It is opt-in
  (``-standard``) because it depends on planner statistics and runner load.
  Run it on demand with ``--test-tags conversation_search_perf``.
"""

import json

from odoo.tests import tagged
from odoo.tools import SQL

from .common import ConversationSearchCase

INDEX = "conversation_search_mail_message_tsv_idx"


class PlanFixtureCase(ConversationSearchCase):
    """10k-message fixture plus plan helpers shared by both test groups."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cr = cls.env.cr
        cr.execute(
            """
            INSERT INTO mail_message
                   (model, res_id, message_type, body, subject, date,
                    create_date, write_date)
            SELECT 'mail.conversation',
                   (%s::int[])[1 + g %% %s],
                   'comment',
                   '<p>texte ' || md5(g::text) || ' commun'
                       || CASE WHEN g = 5000 THEN ' needleunique' ELSE '' END
                       || '</p>',
                   'Sujet ' || g, now(), now(), now()
              FROM generate_series(1, 10000) g
            """,
            [cls.all_convs.ids, len(cls.all_convs)],
        )
        cr.execute("ANALYZE mail_message")

    def _plan(self, sql, analyze=True):
        options = "ANALYZE, FORMAT JSON" if analyze else "FORMAT JSON"
        self.env.cr.execute(SQL("EXPLAIN (%s) %s", SQL(options), sql))
        plan = self.env.cr.fetchone()[0]
        if isinstance(plan, str):
            plan = json.loads(plan)
        return plan[0]

    def _nodes(self, node):
        yield node
        for child in node.get("Plans", []):
            yield from self._nodes(child)

    def _assert_index_in_plan(self, plan):
        nodes = list(self._nodes(plan["Plan"]))
        # The index must be probed with the full-text match itself. Merely
        # listing it is not enough: a partial index can be scanned wholesale
        # for its predicate (no Index Cond) when the expression differs.
        self.assertTrue(
            [
                n
                for n in nodes
                if n.get("Index Name") == INDEX and "@@" in n.get("Index Cond", "")
            ],
            "GIN index not probed with the @@ match",
        )
        self.assertFalse(
            [
                n
                for n in nodes
                if n["Node Type"] == "Seq Scan"
                and n.get("Relation Name") == "mail_message"
            ]
        )

    def _queries(self):
        """The two real SQL statements behind the search paths."""
        self.backend._fts_flush()
        domain_sql = self.Conversation._search(
            [("message_content", "ilike", "needleunique")]
        ).select()
        ranked_sql = self.backend._fts_ranked_sql("needleunique")
        return domain_sql, ranked_sql


@tagged("post_install", "-at_install")
class TestIndexPlan(PlanFixtureCase):
    """Deterministic eligibility proof (see module docstring)."""

    def _restrict_planner(self):
        """Leave the GIN index as the only non-seq access path to mail_message.

        Everything here is transactional DDL / ``SET LOCAL``: it is undone by
        the test's savepoint rollback and never visible to other tests.
        """
        cr = self.env.cr
        cr.execute(
            """
            SELECT i.indexrelid::regclass::text
              FROM pg_index i
              JOIN pg_class c ON c.oid = i.indexrelid
             WHERE i.indrelid = 'mail_message'::regclass
               AND c.relname <> %s
               AND NOT EXISTS (SELECT 1 FROM pg_constraint k
                                WHERE k.conindid = i.indexrelid)
            """,
            [INDEX],
        )
        for (index_name,) in cr.fetchall():
            cr.execute(SQL("DROP INDEX %s", SQL(index_name)))
        for setting in ("enable_seqscan", "enable_indexscan", "enable_indexonlyscan"):
            cr.execute(SQL("SET LOCAL %s = off", SQL.identifier(setting)))

    def _assert_gin_eligible(self, sql):
        self._restrict_planner()
        self._assert_index_in_plan(self._plan(sql, analyze=False))

    def test_domain_path_uses_gin_index(self):
        domain_sql, _ranked_sql = self._queries()
        self._assert_gin_eligible(domain_sql)

    def test_ranked_path_uses_gin_index_selective_term(self):
        _domain_sql, ranked_sql = self._queries()
        self._assert_gin_eligible(ranked_sql)

    def test_ranked_path_worst_case_all_rows_match(self):
        self.backend._fts_flush()
        self.assertEqual(
            len(self.search_api("commun", limit=80)),
            80 if len(self.all_convs) >= 80 else len(self.all_convs),
        )

    # -- the proof above must fail when the index cannot serve the query ----
    def test_proof_fails_when_index_is_dropped(self):
        domain_sql, ranked_sql = self._queries()
        self.env.cr.execute(SQL("DROP INDEX %s", SQL.identifier(INDEX)))
        for sql in (domain_sql, ranked_sql):
            with self.assertRaises(AssertionError):
                self._assert_gin_eligible(sql)

    def test_proof_fails_when_expression_does_not_match_index(self):
        self.backend._fts_flush()
        sql = SQL(
            "SELECT m.res_id FROM mail_message m "
            "WHERE m.model = 'mail.conversation' "
            "AND to_tsvector('simple', m.body) @@ %s",
            self.backend._fts_tsquery("needleunique"),
        )
        with self.assertRaises(AssertionError):
            self._assert_gin_eligible(sql)

    def test_proof_fails_when_partial_predicate_is_not_implied(self):
        self.backend._fts_flush()
        sql = SQL(
            "SELECT m.res_id FROM mail_message m WHERE %s @@ %s",
            self.backend._fts_tsv(),
            self.backend._fts_tsquery("needleunique"),
        )
        with self.assertRaises(AssertionError):
            self._assert_gin_eligible(sql)


@tagged("post_install", "-at_install", "-standard", "conversation_search_perf")
class TestIndexPerf(PlanFixtureCase):
    """Opt-in: real-planner plan + wall-clock checks on 10,000 messages.

    ``--test-tags conversation_search_perf``
    """

    def _assert_fast_indexed(self, sql, limit_ms=1000):
        plan = self._plan(sql)
        self._assert_index_in_plan(plan)
        self.assertLess(plan["Execution Time"], limit_ms)

    def test_domain_path_fast_with_gin_index(self):
        domain_sql, _ranked_sql = self._queries()
        self._assert_fast_indexed(domain_sql)

    def test_ranked_path_fast_with_gin_index_selective_term(self):
        _domain_sql, ranked_sql = self._queries()
        self._assert_fast_indexed(ranked_sql)

    def test_ranked_path_worst_case_all_rows_match_is_fast(self):
        self.backend._fts_flush()
        plan = self._plan(self.backend._fts_ranked_sql("commun", limit=80))
        self.assertLess(plan["Execution Time"], 1000)
