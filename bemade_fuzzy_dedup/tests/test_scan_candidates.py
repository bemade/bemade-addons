"""Acceptance criteria: which pairs a scan proposes.

1.  Two records whose values are similar above the threshold are proposed.
2.  Two records whose values are *identical* are proposed. This engine runs a
    single pass, so unlike the Enterprise arrangement there is no exact-match
    rule pass upstream of it -- excluding equal pairs here would mean exact
    duplicates are never found at all.
3.  Two records whose values fall below the threshold are not proposed.
4.  Records excluded by the target's domain are not proposed.
5.  Archived records are not proposed.
6.  Records with an empty or NULL value are not proposed, and never group
    together with each other.
7.  On a model with ``parent_id``, two records under *different* parents are
    never paired however similar their values. Child records are commonly
    named for a role rather than an identity, and comparing across parents
    collapses hundreds of unrelated records into one group.
8.  A record is never paired with itself.
9.  Where ``pg_trgm`` is unavailable the scan returns nothing and logs, rather
    than raising.
"""

from unittest.mock import patch

from odoo.tests import tagged

from .common import SCOPE, FuzzyDedupCase


@tagged("post_install", "-at_install")
class TestScanCandidates(FuzzyDedupCase):
    def test_01_similar_above_threshold_proposed(self):
        a = self._partner("Northwind Trading Company")
        b = self._partner("Northwind Trading Compny")
        self.assertIn(frozenset((a.id, b.id)), self._pairs(self._target()))

    def test_02_identical_values_proposed(self):
        a = self._partner("Acme Industrial", name="Acme Industrial 1")
        b = self._partner("Acme Industrial", name="Acme Industrial 2")
        self.assertIn(
            frozenset((a.id, b.id)),
            self._pairs(self._target()),
            "a single-pass engine has no exact-match pass upstream, so equal "
            "values must be proposed here or never at all",
        )

    def test_03_below_threshold_not_proposed(self):
        a = self._partner("Northwind Trading Company")
        b = self._partner("Zebra Logistics Group")
        self.assertNotIn(frozenset((a.id, b.id)), self._pairs(self._target()))

    def test_04_domain_excludes_records(self):
        a = self._partner("Copperfield Metals")
        b = self._partner("Copperfield Metals", name="out of scope")
        b.function = "SOMETHING-ELSE"
        self.assertNotIn(frozenset((a.id, b.id)), self._pairs(self._target()))

    def test_05_archived_records_excluded(self):
        a = self._partner("Silverline Freight")
        b = self._partner("Silverline Freight", name="archived")
        b.active = False
        self.assertNotIn(frozenset((a.id, b.id)), self._pairs(self._target()))

    def test_06_empty_values_never_group(self):
        a = self._partner(False, name="no ref A")
        b = self._partner(False, name="no ref B")
        c = self._partner("", name="blank ref C")
        pairs = self._pairs(self._target())
        for left, right in ((a, b), (a, c), (b, c)):
            self.assertNotIn(frozenset((left.id, right.id)), pairs)

    def test_07_never_pairs_across_parents(self):
        parent_a = self._partner("PARENT-A", name="Parent A", is_company=True)
        parent_b = self._partner("PARENT-B", name="Parent B", is_company=True)
        under_a = self._partner("Accounts Payable", name="AP A", parent_id=parent_a.id)
        under_b = self._partner("Accounts Payable", name="AP B", parent_id=parent_b.id)
        sibling = self._partner("Accounts Payable", name="AP A2", parent_id=parent_a.id)
        pairs = self._pairs(self._target())
        self.assertNotIn(
            frozenset((under_a.id, under_b.id)),
            pairs,
            "role names under different parents are different people",
        )
        self.assertIn(
            frozenset((under_a.id, sibling.id)),
            pairs,
            "records under the SAME parent are still comparable",
        )

    def test_08_never_pairs_a_record_with_itself(self):
        self._partner("Lonely Holdings")
        pairs = self._pairs(self._target())
        self.assertFalse([p for p in pairs if len(p) < 2])

    def test_09_degrades_without_pg_trgm(self):
        self._partner("Northwind Trading Company")
        self._partner("Northwind Trading Compny")
        target = self._target()
        with patch.object(type(target), "_ensure_pg_trgm", return_value=False):
            self.assertEqual(target._candidate_pairs(), [])
