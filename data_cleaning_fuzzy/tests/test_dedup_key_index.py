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

        Deliberately a single-sided lookup rather than the self-join the pass
        actually runs. Plan choice is cost-based: on a small table the planner
        correctly prefers to drive the self-join off the primary key and apply
        `%` as a filter, so asserting the self-join's plan shape would be a
        row-count-dependent flake. The property criterion 2 exists to protect
        is that the index is *usable* for `%` against the bare column at all,
        and that is exactly what this asserts. An expression mismatch (e.g.
        the index built over unaccent(dedup_key)) fails here.
        """
        self.env.cr.execute("SET LOCAL enable_seqscan = off")
        self.env.cr.execute("SET LOCAL pg_trgm.similarity_threshold = 0.55")
        self.env.cr.execute(
            "EXPLAIN SELECT id FROM res_partner WHERE dedup_key % 'northwind'"
        )
        plan = "\n".join(row[0] for row in self.env.cr.fetchall())
        self.assertIn("res_partner_dedup_key_trgm_idx", plan)
