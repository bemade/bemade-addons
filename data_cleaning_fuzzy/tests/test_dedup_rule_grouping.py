"""A deduplication rule on dedup_key groups near-duplicates (stage 1).

ACCEPTANCE CRITERIA
===================

Stage 1 adds no new grouping engine; it points the standard one at a better
field. These tests assert that premise end to end, through the real
``data_merge.model.find_duplicates()``, using the duplicate shapes actually
observed in the real migration data.

1. Partners differing only by legal suffix are grouped.
   "Northwind" + "Northwind Inc."
2. Partners differing only by punctuation are grouped.
   "A & B Filtration" + "A&B Filtration"
3. Partners differing only by case are grouped.
   "TechFab Systems" + "Techfab Systems Inc."
4. Partners with genuinely different names are NOT grouped.
   "Alpha Tools" + "Beta Systems"
5. Records whose key is False are never grouped, however many share that
   state. (Pairs with criterion 6 of the normalization suite -- together these
   are what stop every junk record collapsing into one group.)
6. Archived partners are excluded, matching standard engine behaviour
   (``find_duplicates`` searches with the default ``active_test``).
7. Running find_duplicates twice does not create duplicate groups for the
   same set of records.
8. The shipped deduplication model excludes child contacts. Contacts under a
   company are commonly named after a role ("Accounts Payable", "Reception"),
   so they share a deduplication key while being different people at
   different companies. Without this scope a real ~36k-partner database
   produced single groups of 811, 729 and 596 records of pure role names.

NON-CRITERIA
------------
That a ``data_merge.rule`` record can be created with our field, or that the
manifest depends on ``data_cleaning``, are declarations rather than logic and
are not tested. The behavioural assertions above cover them implicitly: they
cannot pass unless both hold.
"""

from odoo.tests.common import TransactionCase


class TestDedupRuleGrouping(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dm_model = cls.env.ref("data_cleaning_fuzzy.data_merge_model_partner_key")
        # Capture the shipped domain before overriding it: the tests below
        # mutate this record, so it cannot be read back afterwards.
        cls.shipped_domain = cls.dm_model.domain
        # Isolate from any partner already in the database.
        cls.dm_model.domain = "[('ref', '=', 'dcf-test')]"

    def _partners(self, *names, **vals):
        return self.env["res.partner"].create(
            [dict(vals, name=n, ref="dcf-test") for n in names]
        )

    def _grouped_ids(self):
        self.dm_model.find_duplicates()
        groups = self.env["data_merge.group"].search(
            [("model_id", "=", self.dm_model.id)]
        )
        return [set(g.record_ids.mapped("res_id")) for g in groups]

    def test_groups_records_differing_by_legal_suffix(self):
        """Criterion 1."""
        a, b = self._partners("Northwind", "Northwind Inc.")
        self.assertIn({a.id, b.id}, self._grouped_ids())

    def test_groups_records_differing_by_punctuation(self):
        """Criterion 2."""
        a, b = self._partners("A & B Filtration", "A&B Filtration")
        self.assertIn({a.id, b.id}, self._grouped_ids())

    def test_groups_records_differing_by_case(self):
        """Criterion 3."""
        a, b = self._partners("TechFab Systems", "Techfab Systems Inc.")
        self.assertIn({a.id, b.id}, self._grouped_ids())

    def test_does_not_group_distinct_names(self):
        """Criterion 4."""
        self._partners("Alpha Tools", "Beta Systems")
        self.assertEqual(self._grouped_ids(), [])

    def test_false_keys_are_never_grouped(self):
        """Criterion 5."""
        self._partners("Inc.", "...", "Ltd")
        self.assertEqual(self._grouped_ids(), [])

    def test_archived_partners_excluded(self):
        """Criterion 6."""
        a, b = self._partners("Northwind", "Northwind Inc.")
        b.active = False
        self.assertEqual(self._grouped_ids(), [])

    def test_rerun_is_idempotent(self):
        """Criterion 7."""
        self._partners("Northwind", "Northwind Inc.")
        first = self._grouped_ids()
        second = self._grouped_ids()
        self.assertEqual(len(first), 1)
        self.assertEqual(second, first)

    def test_shipped_model_excludes_child_contacts(self):
        """Criterion 8."""
        self.assertIn(
            "parent_id",
            self.shipped_domain,
            "the shipped model must exclude child contacts",
        )
        acme, globex = self._partners("Acme Industries", "Globex Industries")
        (acme + globex).write({"is_company": True})
        for parent in (acme, globex):
            self.env["res.partner"].create(
                {"name": "Accounts Payable", "parent_id": parent.id, "ref": "dcf-test"}
            )
        self.dm_model.domain = "[('ref', '=', 'dcf-test'), ('parent_id', '=', False)]"
        for group in self._grouped_ids():
            names = self.env["res.partner"].browse(list(group)).mapped("name")
            self.assertNotIn("Accounts Payable", names)
