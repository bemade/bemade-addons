"""Acceptance criteria: how pairs become reviewable groups, across re-runs.

Groups are persistent, which is the whole reason this engine does not reuse
core's transient ``base.partner.merge.line``. Persistence is only worth
anything if a re-scan respects what the reviewer already decided.

1.  Pairs sharing a record are clustered transitively: A~B and B~C yield one
    group of three, not two groups of two.
2.  A scan that finds a pair already covered by an existing group creates no
    new group.
3.  A group the reviewer *discarded* is not proposed again by a later scan.
    Rejected candidates reappearing every night is what makes a dedup tool get
    abandoned.
4.  A group whose records were already merged is not proposed again.
5.  A scan finding a strictly larger cluster than an existing group does
    create the larger group -- new information is not suppressed by an old
    subset.
6.  Each new group elects a master: the oldest record by ``create_date``.
7.  A group is created only for clusters of two or more records.
8.  Groups proposed before similarity was recorded can be scored after the
    fact. A re-scan will not do it — the subset check skips clusters already
    grouped — so an explicit backfill is the only way those groups ever become
    rankable.
"""

from odoo.tests import tagged

from .common import FuzzyDedupCase


@tagged("post_install", "-at_install")
class TestScanClustering(FuzzyDedupCase):
    def _res_ids(self, group):
        return set(group.record_ids.mapped("res_id"))

    def test_01_transitive_clustering(self):
        a = self._partner("Global Milling and Consulting")
        b = self._partner("Global Milling and Consultng")
        c = self._partner("Global Milling and Consuling")
        groups = self._target()._scan()
        self.assertEqual(len(groups), 1, "one cluster, not one group per pair")
        self.assertEqual(self._res_ids(groups), {a.id, b.id, c.id})

    def test_02_rescan_creates_no_duplicate_group(self):
        self._partner("Halcyon Bearings")
        self._partner("Halcyon Bearngs")
        target = self._target()
        self.assertEqual(len(target._scan()), 1)
        self.assertEqual(len(target._scan()), 0, "the same cluster came back")

    def test_03_discarded_group_stays_discarded(self):
        self._partner("Ridgeline Plastics")
        self._partner("Ridgeline Plastcs")
        target = self._target()
        target._scan().action_discard()
        self.assertEqual(
            len(target._scan()), 0, "a rejected group must not be re-proposed"
        )

    def test_04_merged_group_not_reproposed(self):
        self._partner("Beacon Hydraulics")
        self._partner("Beacon Hydralics")
        target = self._target()
        group = target._scan()
        group.state = "merged"
        self.assertEqual(len(target._scan()), 0)

    def test_05_larger_cluster_still_proposed(self):
        a = self._partner("Tanner Woodworks")
        b = self._partner("Tanner Woodwrks")
        target = self._target()
        first = target._scan()
        self.assertEqual(self._res_ids(first), {a.id, b.id})
        c = self._partner("Tanner Woodwors")
        second = target._scan()
        self.assertEqual(len(second), 1, "a strictly larger cluster is new information")
        self.assertEqual(self._res_ids(second), {a.id, b.id, c.id})

    def test_06_elects_oldest_record_as_master(self):
        first = self._partner("Cascade Fasteners")
        self._partner("Cascade Fastners")
        group = self._target()._scan()
        master = group.record_ids.filtered("is_master")
        self.assertEqual(len(master), 1, "exactly one master")
        self.assertEqual(master.res_id, first.id)

    def test_07_no_group_for_a_lone_record(self):
        self._partner("Solitary Instruments")
        self.assertEqual(len(self._target()._scan()), 0)

    def test_08_backfill_scores_unscored_groups(self):
        self._partner("Thornbury Castings")
        self._partner("Thornbury Castngs")
        target = self._target()
        group = target._scan()
        expected = group.similarity
        self.assertGreater(expected, 0.0, "a fresh scan scores the group")

        # Simulate a group proposed by a version that did not record scores.
        self.env.cr.execute(
            "UPDATE bemade_dedup_group SET similarity = 0 WHERE id = %s", (group.id,)
        )
        group.invalidate_recordset(["similarity"])
        self.assertEqual(group.similarity, 0.0)

        self.assertEqual(
            len(target._scan()), 0, "a re-scan does not revisit existing groups"
        )
        group.invalidate_recordset(["similarity"])
        self.assertEqual(group.similarity, 0.0, "so it cannot rescore them either")

        target._backfill_similarity()
        group.invalidate_recordset(["similarity"])
        self.assertAlmostEqual(group.similarity, expected, places=2)

    def test_09_backfill_leaves_scored_groups_alone(self):
        self._partner("Ellersley Foundry")
        self._partner("Ellersley Foundy")
        target = self._target()
        group = target._scan()
        scored = group.similarity
        target._backfill_similarity()
        group.invalidate_recordset(["similarity"])
        self.assertAlmostEqual(group.similarity, scored, places=2)
