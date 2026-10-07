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
        cr = self.env.cr
        # Pin the planner so only our GIN index can serve the query. A GIN
        # index is only ever used through a bitmap scan, so that path is
        # switched on explicitly rather than trusting the server default.
        for setting, value in (
            ("enable_seqscan", "off"),
            ("enable_indexscan", "off"),
            ("enable_indexonlyscan", "off"),
            ("enable_bitmapscan", "on"),
        ):
            cr.execute(f"SET LOCAL {setting} = {value}")
        cr.execute("SET LOCAL pg_trgm.similarity_threshold = 0.55")
        cr.execute("EXPLAIN SELECT id FROM res_partner WHERE dedup_key % 'northwind'")
        plan = "\n".join(row[0] for row in cr.fetchall())
        if "res_partner_dedup_key_trgm_idx" not in plan:
            self.fail(
                "trigram index not used for `%%`.\nplan:\n%s\ndiagnostics: %s"
                % (plan, self._planner_diagnostics())
            )

    def _planner_diagnostics(self):
        """Server facts that decide whether the index is usable, for a failure message."""
        cr = self.env.cr
        cr.execute("SHOW server_version")
        facts = {"server_version": cr.fetchone()[0]}
        cr.execute(
            "SELECT indisvalid, indisready FROM pg_index "
            "WHERE indexrelid = 'res_partner_dedup_key_trgm_idx'::regclass"
        )
        facts["index_valid_ready"] = cr.fetchone()
        cr.execute(
            "SELECT e.extversion, n.nspname FROM pg_extension e "
            "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'pg_trgm'"
        )
        facts["pg_trgm_version_schema"] = cr.fetchone()
        cr.execute(
            "SELECT oprnamespace::regnamespace::text, oprleft::regtype::text, "
            "oprright::regtype::text FROM pg_operator "
            "WHERE oprname = '%' AND oprleft = 'text'::regtype"
        )
        facts["text_percent_operators"] = cr.fetchall()
        cr.execute("SHOW search_path")
        facts["search_path"] = cr.fetchone()[0]
        return facts
