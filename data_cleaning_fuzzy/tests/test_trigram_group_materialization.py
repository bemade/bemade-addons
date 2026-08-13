"""Trigram pairs become reviewable data_merge groups (stage 2).

ACCEPTANCE CRITERIA
===================

Rather than override ``find_duplicates``, the trigram pass writes standard
``data_merge.group`` / ``data_merge.record`` rows. Everything downstream --
scoring, master election, the review UI, the merge itself -- is then Odoo's
existing code. These criteria assert the handoff is well formed.

1. A proposed pair produces one ``data_merge.group`` with one
   ``data_merge.record`` per partner, linked to the correct
   ``data_merge.model``.
2. The group's ``similarity`` is populated. It is a stored compute on the
   group, so our rows must be written such that it fires; a group showing 0%
   in the review list is a defect even if its records are right.
3. A master record is elected, as for engine-created groups.
4. The group merges through the standard flow and archives/removes the
   non-master partners per the model's ``removal_mode``.
5. Re-running the pass does not create a second group for a pair that is
   already grouped.
6. Re-running does not resurrect a group the user has discarded. Discarded
   pairs must stay discarded, or the queue becomes impossible to clear.
7. Transitively linked pairs collapse into a single group rather than
   several overlapping ones -- if a~b and b~c are both proposed, the result is
   one group of three, matching how the engine merges overlapping candidate
   lists.
8. The pass never merges anything by itself, regardless of similarity or of
   the deduplication model's ``merge_mode``. Stage 2 proposes; a human
   disposes.

NON-CRITERIA
------------
Merge mechanics (field survivorship, reference reassignment) belong to
``data_merge`` and are not retested here. Criterion 4 asserts only that our
groups are compatible with that machinery.
"""

from odoo.tests.common import TransactionCase


class TestTrigramGroupMaterialization(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dm_model = cls.env.ref("data_cleaning_fuzzy.data_merge_model_partner_key")
        cls.dm_model.domain = "[('ref', '=', 'dcf-test')]"

    def _partners(self, *names, **vals):
        return self.env["res.partner"].create(
            [dict(vals, name=n, ref="dcf-test") for n in names]
        )

    def _groups(self):
        return self.env["data_merge.group"].search(
            [("model_id", "=", self.dm_model.id)]
        )

    def _run(self):
        self.dm_model._find_fuzzy_duplicates()
        return self._groups()

    def _similar_pair(self):
        return self._partners(
            "Global Milling and Consulting", "Global Milling & Consulting LLC"
        )

    def test_pair_produces_wellformed_group(self):
        """Criterion 1."""
        a, b = self._similar_pair()
        groups = self._run()
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups.model_id, self.dm_model)
        self.assertEqual(set(groups.record_ids.mapped("res_id")), {a.id, b.id})

    def test_group_similarity_is_computed(self):
        """Criterion 2."""
        self._similar_pair()
        self.assertTrue(self._run().similarity > 0)

    def test_master_record_is_elected(self):
        """Criterion 3."""
        self._similar_pair()
        masters = self._run().record_ids.filtered("is_master")
        self.assertEqual(len(masters), 1)

    def test_group_merges_through_standard_flow(self):
        """Criterion 4."""
        a, b = self._similar_pair()
        group = self._run()
        master_id = group.record_ids.filtered("is_master").res_id
        group.merge_records()
        survivors = (a + b).exists().filtered("active")
        self.assertEqual(survivors.ids, [master_id])

    def test_rerun_does_not_duplicate_groups(self):
        """Criterion 5."""
        self._similar_pair()
        self.assertEqual(len(self._run()), 1)
        self.assertEqual(len(self._run()), 1)

    def test_rerun_does_not_resurrect_discarded_groups(self):
        """Criterion 6."""
        a, b = self._similar_pair()
        self._run().discard_records()
        self._run()
        live = self.env["data_merge.record"].search(
            [
                ("model_id", "=", self.dm_model.id),
                ("res_id", "in", [a.id, b.id]),
                ("is_discarded", "=", False),
            ]
        )
        self.assertFalse(live, "a discarded pair was proposed again")

    def test_transitive_pairs_collapse_into_one_group(self):
        """Criterion 7."""
        self._partners(
            "Orion Prints and Technologies Pvt Ltd",
            "Orion Prints & Technology Pvt. Ltd.",
            "Orion Prints and Technology Pvt Ltd",
        )
        groups = self._run()
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups.record_ids), 3)

    def test_pass_never_merges_automatically(self):
        """Criterion 8."""
        a, b = self._similar_pair()
        self.dm_model.merge_mode = "automatic"
        self.dm_model.merge_threshold = 1
        self._run()
        self.assertTrue(a.active and b.active, "the pass must never merge")
        self.assertEqual(len(self._groups()), 1)
