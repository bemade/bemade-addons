"""Acceptance criteria: a target owns the trigram index for its column.

Enabling a model is the only configuration step, so it has to carry its own
infrastructure. Creating a target must leave the column queryable by trigram
similarity; deleting it must leave no index behind.

1.  Creating a target on a plain ``char`` column creates a GIN index using
    ``gin_trgm_ops`` on that column, and records its name on the target.
2.  Creating a target on a *translated* column indexes the ``en_US`` value
    (``field->>'en_US'``), not the raw JSONB. Odoo 19 stores translated fields
    as JSONB, and a trigram index over the whole document would match on keys
    and other languages.
3.  The scan's comparison expression matches the indexed expression exactly.
    A mismatch does not fail -- it silently falls back to a sequential scan --
    so this is asserted rather than left to observation.
4.  Deleting a target drops its index.
5.  Two targets on different models whose field shares a name do not collide
    on index name.
6.  Where ``pg_trgm`` cannot be created, creating a target still succeeds and
    is still configurable; only the scan is skipped. Aborting instead would
    take the whole registry load down with "operator class gin_trgm_ops does
    not exist", which is a far worse failure than not having the feature.
"""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


def _normalize(sql):
    """Compare SQL expressions modulo the reformatting pg_indexes applies."""
    return sql.replace('"', "").replace(" ", "").replace("::text", "")


@tagged("post_install", "-at_install")
class TestTargetIndex(TransactionCase):
    def _indexdef(self, name):
        self.env.cr.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = %s", (name,)
        )
        row = self.env.cr.fetchone()
        return row[0] if row else None

    def _target(self, model, field):
        model_id = self.env["ir.model"]._get_id(model)
        return self.env["bemade.dedup.target"].create(
            {
                "model_id": model_id,
                "field_id": self.env["ir.model.fields"]._get(model, field).id,
            }
        )

    def test_01_plain_char_column_indexed(self):
        target = self._target("res.partner", "ref")
        self.assertTrue(target.index_name)
        indexdef = self._indexdef(target.index_name)
        self.assertIsNotNone(indexdef, "the index was not created")
        self.assertIn("gin", indexdef.lower())
        self.assertIn("gin_trgm_ops", indexdef)
        self.assertIn("ref", indexdef)

    def test_02_translated_column_indexes_en_us(self):
        self.assertTrue(
            self.env["ir.model.fields"]._get("res.country", "name").translate,
            "res.country.name is expected to be a translated field",
        )
        target = self._target("res.country", "name")
        indexdef = self._indexdef(target.index_name)
        self.assertIsNotNone(indexdef, "the index was not created")
        self.assertIn("en_US", indexdef)
        self.assertIn("gin_trgm_ops", indexdef)

    def test_03_scan_expression_matches_index(self):
        for model, field in (("res.partner", "ref"), ("res.country", "name")):
            with self.subTest(model=model):
                target = self._target(model, field)
                indexdef = self._indexdef(target.index_name)
                self.assertIn(
                    _normalize(target._trgm_expression()),
                    _normalize(indexdef),
                    "scan expression must match the indexed expression, or the "
                    "index is silently unused",
                )

    def test_04_unlink_drops_index(self):
        target = self._target("res.partner", "ref")
        name = target.index_name
        self.assertIsNotNone(self._indexdef(name))
        target.unlink()
        self.assertIsNone(self._indexdef(name), "the index outlived its target")

    def test_05_same_field_name_different_models_no_collision(self):
        partner = self._target("res.partner", "name")
        country = self._target("res.country", "name")
        self.assertNotEqual(partner.index_name, country.index_name)
        self.assertIsNotNone(self._indexdef(partner.index_name))
        self.assertIsNotNone(self._indexdef(country.index_name))

    def test_06_degrades_without_pg_trgm(self):
        with patch.object(
            type(self.env["bemade.dedup.target"]),
            "_ensure_pg_trgm",
            return_value=False,
        ):
            target = self._target("res.partner", "ref")
        self.assertTrue(target.exists(), "target creation must not abort")
        self.assertFalse(target.index_name, "no index should be claimed")
