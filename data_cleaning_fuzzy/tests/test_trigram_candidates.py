"""The trigram pass selects candidate pairs (stage 2).

ACCEPTANCE CRITERIA
===================

Normalized keys still require the surviving characters to match exactly.
Stage 2 compares every pair of keys by trigram similarity and proposes those
above a threshold. These criteria cover pair SELECTION; materialising the
results into review groups is covered in test_trigram_group_materialization.

1. Pairs scoring at or above the threshold are proposed. Observed examples:
       "Global Milling and Consulting" / "Global Milling & Consulting LLC"
       "Orion Prints & Technology Pvt. Ltd." / "Orion Prints and Technologies Pvt Ltd"
   Neither is reachable by any key-equality strategy -- "and" vs "&" and
   "Technology" vs "Technologies" survive normalization.
2. Pairs scoring below the threshold are not proposed.
3. The threshold is read from an ``ir.config_parameter`` and is honoured:
   raising it strictly reduces the proposed set.
4. A missing or unparseable parameter falls back to the documented default
   rather than raising or proposing everything. A malformed value must not be
   silently read as 0.0, which would propose every pair in the database.
5. Pairs already grouped by stage 1 are not proposed again -- identical keys
   score 1.0 and would otherwise all reappear here.
6. Archived partners are excluded.
7. Records with a False key are excluded.
8. Each unordered pair is proposed once; (a,b) and (b,a) are the same pair.

NON-CRITERIA
------------
Precision is explicitly NOT asserted. At the default threshold the pass
proposes true near-duplicates alongside items such as "BMO Mastercard" /
"BMO Mastercard 1893", which are distinct cards. This is understood and
accepted: output is a review queue, merging stays manual, and the threshold is
tunable. A test asserting a particular precision rate would encode one
dataset's accidents as a contract.
"""

from odoo.addons.data_cleaning_fuzzy.models.data_merge_model import (
    DEFAULT_THRESHOLD,
    THRESHOLD_PARAM,
)
from odoo.tests.common import TransactionCase


class TestTrigramCandidates(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dm_model = cls.env.ref("data_cleaning_fuzzy.data_merge_model_partner_key")
        cls.dm_model.domain = "[('ref', '=', 'dcf-test')]"

    def _partners(self, *names, **vals):
        return self.env["res.partner"].create(
            [dict(vals, name=n, ref="dcf-test") for n in names]
        )

    def _pairs(self):
        return {frozenset(p) for p in self.dm_model._fuzzy_candidate_pairs()}

    def test_proposes_pairs_above_threshold(self):
        """Criterion 1."""
        a, b = self._partners(
            "Global Milling and Consulting", "Global Milling & Consulting LLC"
        )
        c, d = self._partners(
            "Orion Prints & Technology Pvt. Ltd.",
            "Orion Prints and Technologies Pvt Ltd",
        )
        pairs = self._pairs()
        self.assertIn(frozenset({a.id, b.id}), pairs)
        self.assertIn(frozenset({c.id, d.id}), pairs)

    def test_ignores_pairs_below_threshold(self):
        """Criterion 2."""
        a, b = self._partners("Alpha Tools", "Halden Canada")
        self.assertNotIn(frozenset({a.id, b.id}), self._pairs())

    def test_threshold_is_configurable(self):
        """Criterion 3."""
        self._partners(
            "Global Milling and Consulting", "Global Milling & Consulting LLC"
        )
        param = self.env["ir.config_parameter"].sudo()
        param.set_param(THRESHOLD_PARAM, "0.4")
        loose = self._pairs()
        param.set_param(THRESHOLD_PARAM, "0.99")
        strict = self._pairs()
        self.assertTrue(strict < loose, "raising the threshold must narrow the set")

    def test_malformed_threshold_falls_back_to_default(self):
        """Criterion 4 - must not degrade to 0.0."""
        param = self.env["ir.config_parameter"].sudo()
        for bad in ("not-a-number", "", "0", "-1", "5"):
            param.set_param(THRESHOLD_PARAM, bad)
            self.assertEqual(
                self.dm_model._fuzzy_threshold(),
                DEFAULT_THRESHOLD,
                "threshold %r should fall back to the default" % bad,
            )

    def test_excludes_pairs_already_grouped_by_exact_key(self):
        """Criterion 5."""
        a, b = self._partners("Northwind", "Northwind Inc.")
        self.assertEqual(a.dedup_key, b.dedup_key)
        self.assertNotIn(frozenset({a.id, b.id}), self._pairs())

    def test_excludes_archived_partners(self):
        """Criterion 6."""
        a, b = self._partners(
            "Global Milling and Consulting", "Global Milling & Consulting LLC"
        )
        b.active = False
        self.assertNotIn(frozenset({a.id, b.id}), self._pairs())

    def test_excludes_false_keys(self):
        """Criterion 7."""
        a, b = self._partners("Inc.", "Ltd")
        self.assertFalse(a.dedup_key)
        self.assertFalse(b.dedup_key)
        self.assertNotIn(frozenset({a.id, b.id}), self._pairs())

    def test_pairs_are_unordered_and_proposed_once(self):
        """Criterion 8."""
        self._partners(
            "Global Milling and Consulting", "Global Milling & Consulting LLC"
        )
        raw = self.dm_model._fuzzy_candidate_pairs()
        self.assertEqual(len(raw), len({frozenset(p) for p in raw}))
