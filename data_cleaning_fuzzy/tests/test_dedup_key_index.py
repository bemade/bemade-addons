"""The GIN trigram index on dedup_key exists with a stable expression.

ACCEPTANCE CRITERIA
===================

The trigram pass joins on ``a.dedup_key % b.dedup_key``. PostgreSQL only uses
a trigram index when the indexed expression matches the queried one. Measured
on 837 partners: 687 ms without the index, 20 ms with it. A mismatch is
therefore not a crash but a silent 30x slowdown, which is exactly the kind of
regression that survives review.

1. After install, a GIN index using ``gin_trgm_ops`` exists on
   ``res_partner.dedup_key``.
2. The indexed expression is the BARE column, not ``unaccent(dedup_key)``.

   This is deliberate and is the reason the index is declared explicitly
   rather than via ``fields.Char(index="trigram")``. Odoo's own index
   generator wraps the column in ``unaccent()`` when, and only when,
   ``registry.has_unaccent == FunctionStatus.INDEXABLE``
   (``odoo/orm/registry.py``). That status depends on whether a superuser has
   run ``ALTER FUNCTION unaccent(text) IMMUTABLE`` on the database -- which
   differs across our fleet and can change under us. Letting the expression
   track that flag would silently un-index this query the day the extension is
   made immutable. ``dedup_key`` is already accent-folded in Python, so
   ``unaccent()`` on it is a no-op and we lose nothing by pinning.

3. The query planner actually chooses the index for the trigram self-join.
   Asserting the index exists is not enough; criterion 2 only matters because
   of its effect here.

NON-CRITERIA
------------
Absolute timings are not asserted -- they are hardware-dependent and flaky.
Plan shape is the stable signal.
"""

import re

from odoo.tests.common import TransactionCase


class TestDedupKeyIndex(TransactionCase):
    def _index_def(self):
        self.env.cr.execute(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = 'res_partner' AND indexname = %s",
            ("res_partner_dedup_key_trgm_idx",),
        )
        row = self.env.cr.fetchone()
        return row[0] if row else None

    def test_gin_trigram_index_exists(self):
        """Criterion 1."""
        indexdef = self._index_def()
        self.assertIsNotNone(indexdef, "trigram index on dedup_key is missing")
        self.assertIn("gin", indexdef.lower())
        self.assertIn("gin_trgm_ops", indexdef)

    def test_index_expression_is_bare_column(self):
        """Criterion 2 - must not be wrapped in unaccent()."""
        indexdef = self._index_def()
        self.assertIsNotNone(indexdef)
        self.assertNotIn("unaccent", indexdef.lower())

    def test_index_is_usable_for_similarity_operator(self):
        """Criterion 3 - the planner can drive the `%` operator off our index.

        The real index is recreated on an empty temp table and the plan is
        taken there. The planner skips an index flagged
        ``pg_index.indcheckxmin`` (set when it is built over broken HOT chains,
        as on res_partner during install) until every transaction older than
        its build has ended, cluster-wide. Planning against res_partner
        therefore depends on what else the database server is running. The
        probe has no such history, and the indexed expression and operator
        class still come from the real definition, so an expression mismatch
        (e.g. an index over unaccent(dedup_key)) still fails here.

        A single-sided lookup rather than the self-join the pass runs: on a
        small table the planner rightly drives the self-join off the primary
        key, so that plan shape would be a row-count-dependent flake.
        """
        indexdef = self._index_def()
        self.assertIsNotNone(indexdef, "trigram index on dedup_key is missing")
        probe_def, count = re.subn(
            r"^CREATE INDEX \S+ ON \S+ ",
            "CREATE INDEX dedup_probe_idx ON dedup_probe ",
            indexdef,
        )
        self.assertEqual(count, 1, indexdef)
        cr = self.env.cr
        cr.execute(
            "CREATE TEMP TABLE dedup_probe ON COMMIT DROP AS "
            "SELECT dedup_key FROM res_partner WITH NO DATA"
        )
        cr.execute(probe_def)
        # Pin the planner so only the GIN index can serve the query. A GIN
        # index is only ever used through a bitmap scan, so that path is
        # switched on explicitly rather than trusting the server default.
        for setting, value in (
            ("enable_seqscan", "off"),
            ("enable_indexscan", "off"),
            ("enable_indexonlyscan", "off"),
            ("enable_bitmapscan", "on"),
        ):
            cr.execute(f"SET LOCAL {setting} = {value}")
        cr.execute("EXPLAIN SELECT 1 FROM dedup_probe WHERE dedup_key % 'northwind'")
        plan = "\n".join(row[0] for row in cr.fetchall())
        self.assertIn(
            "dedup_probe_idx", plan, f"index not used for `%`:\n{indexdef}\n{plan}"
        )
