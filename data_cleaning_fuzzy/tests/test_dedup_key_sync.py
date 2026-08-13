"""res.partner.dedup_key stays in sync with the name.

ACCEPTANCE CRITERIA
===================

``dedup_key`` is a stored computed field. A stale key silently removes a
partner from deduplication, so staleness is the failure mode that matters.
What is ours to get wrong here is the ``@api.depends`` declaration -- too
narrow and keys go stale, too broad and every partner write recomputes.

1. Renaming a partner recomputes the key.
2. Clearing the name clears the key to False.
3. Writing a field other than ``name`` does not change the key.
4. Batch creation populates every record's key, not only the first.
   (Guards against a compute that mishandles multi-record recordsets.)

NON-CRITERIA
------------
That a stored computed field is populated on create, or backfilled for
existing rows when the column is added at install, is ORM behaviour with no
code of ours involved -- asserting it would test the framework. The install
backfill is instead verified empirically against real data, since a synthetic
test would have to fake the very scenario it claims to cover.
"""

from odoo.tests.common import TransactionCase


class TestDedupKeySync(TransactionCase):
    def test_key_recomputed_on_rename(self):
        """Criterion 1."""
        partner = self.env["res.partner"].create({"name": "Northwind"})
        self.assertEqual(partner.dedup_key, "northwind")
        partner.name = "Apexcorp Inc."
        self.assertEqual(partner.dedup_key, "apexcorp")

    def test_key_cleared_when_name_cleared(self):
        """Criterion 2."""
        partner = self.env["res.partner"].create(
            {"name": "Shipping dock", "type": "delivery"}
        )
        self.assertTrue(partner.dedup_key)
        partner.name = False
        self.assertFalse(partner.dedup_key)

    def test_key_untouched_by_unrelated_write(self):
        """Criterion 3."""
        partner = self.env["res.partner"].create({"name": "Northwind Inc."})
        partner.write({"city": "Montreal", "comment": "unrelated"})
        self.assertEqual(partner.dedup_key, "northwind")

    def test_batch_create_populates_all_keys(self):
        """Criterion 4."""
        partners = self.env["res.partner"].create(
            [
                {"name": "Northwind Inc."},
                {"name": "Halden Canada Inc."},
                {"name": "A & B Filtration"},
            ]
        )
        self.assertEqual(
            partners.mapped("dedup_key"),
            ["northwind", "haldencanada", "abfiltration"],
        )
