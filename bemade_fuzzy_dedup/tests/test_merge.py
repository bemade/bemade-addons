"""Acceptance criteria: merging a group.

The merge itself delegates to the model-agnostic helpers in ``base``
(``_update_foreign_keys_generic``, ``_update_reference_fields_generic``,
``_update_values``) -- the same ones ``account_merge_wizard`` uses on
``account.account``. These tests assert the delegation is wired correctly and
that disposal behaves, not that Odoo's helpers work.

1.  Merging reassigns foreign keys pointing at the source records to the
    master.
2.  Merging reassigns reference fields (``res_model``/``res_id``) -- notably
    attachments -- to the master.
3.  Fields empty on the master are filled from the sources; fields set on the
    master are left alone.
4.  On a model with ``active``, sources are archived, not deleted.
5.  On a model *without* ``active``, sources are deleted.
6.  The master survives the merge and the group ends in state ``merged``.
7.  The elected master can be overridden before merging, and the override is
    what survives.
8.  Merging is never automatic: no scan, cron, or target configuration causes
    a merge. A similarity score is not an identity proof, so disposal stays
    with the reviewer.
9.  A model defining ``_dedup_merge`` owns the merge entirely, disposal
    included — the generic path must not also run underneath it.
10. Merging a group whose records have since been deleted refuses rather than
    merging the survivors. Silently merging a subset of what the reviewer
    approved is a worse outcome than doing nothing.
"""

from unittest.mock import patch

from odoo.tests import tagged

from .common import FuzzyDedupCase


@tagged("post_install", "-at_install")
class TestMerge(FuzzyDedupCase):
    def _pair(self):
        master = self._partner("Ironbark Castings", name="Ironbark Castings")
        source = self._partner("Ironbark Castngs", name="Ironbark Castings Ltd")
        group = self._target()._scan()
        self.assertEqual(len(group), 1)
        return group, master, source

    def _country_pair(self):
        Country = self.env["res.country"]
        master = Country.create({"name": "Testland Republic", "code": "ZY"})
        source = Country.create({"name": "Testland Republc", "code": "ZZ"})
        target = self._target(
            model="res.country",
            field="name",
            domain="[('code', 'in', ('ZY', 'ZZ'))]",
        )
        group = target._scan()
        self.assertEqual(len(group), 1)
        return group, master, source

    def test_01_foreign_keys_reassigned(self):
        group, master, source = self._pair()
        child = self._partner("child", name="Child Of Source", parent_id=source.id)
        group.action_merge()
        self.assertEqual(child.parent_id, master)

    def test_02_reference_fields_reassigned(self):
        group, master, source = self._pair()
        attachment = self.env["ir.attachment"].create(
            {"name": "proof.pdf", "res_model": "res.partner", "res_id": source.id}
        )
        group.action_merge()
        self.assertEqual(attachment.res_id, master.id)

    def test_03_empty_master_fields_filled_master_wins_otherwise(self):
        group, master, source = self._pair()
        master.write({"website": False, "phone": "+1 555 0100"})
        source.write({"website": "https://ironbark.example", "phone": "+1 555 0199"})
        group.action_merge()
        self.assertEqual(master.website, "https://ironbark.example")
        self.assertEqual(master.phone, "+1 555 0100", "the master's own value wins")

    def test_04_sources_archived_where_model_supports_it(self):
        group, master, source = self._pair()
        group.action_merge()
        self.assertTrue(source.exists(), "the source was deleted, not archived")
        self.assertFalse(source.active)
        self.assertTrue(master.active)

    def test_05_sources_deleted_where_model_has_no_active(self):
        group, master, source = self._country_pair()
        self.assertNotIn("active", source._fields)
        group.action_merge()
        self.assertFalse(source.exists())
        self.assertTrue(master.exists())

    def test_06_master_survives_and_group_is_merged(self):
        group, master, source = self._pair()
        group.action_merge()
        self.assertTrue(master.exists())
        self.assertEqual(group.state, "merged")

    def test_07_master_override_is_honoured(self):
        group, master, source = self._pair()
        group.record_ids.is_master = False
        group.record_ids.filtered(lambda r: r.res_id == source.id).is_master = True
        group.action_merge()
        self.assertFalse(source.active is False and master.active is False)
        self.assertTrue(source.active, "the overridden master must survive")
        self.assertFalse(master.active, "the un-elected record must be archived")

    def test_08_scanning_never_merges(self):
        group, master, source = self._pair()
        self.assertEqual(group.state, "pending")
        self.assertTrue(master.active)
        self.assertTrue(source.active)

    def test_09_stale_group_refuses_to_merge(self):
        group, master, source = self._pair()
        source.unlink()
        group.action_merge()
        self.assertEqual(group.state, "stale")
        self.assertTrue(master.exists())
        self.assertTrue(master.active, "nothing may be merged from a stale group")

    def test_10_model_owned_merge_replaces_the_generic_path(self):
        """Models with their own merge get to use it, untouched.

        crm.lead is the motivating case: _merge_opportunity consolidates
        history and disposes of the losers itself, so running the generic
        foreign-key reassignment underneath it would leave a half-merged
        record.
        """
        group, master, source = self._pair()
        calls = []

        def _dedup_merge(self, sources):
            calls.append((self.id, sources.ids))

        with patch.object(
            type(self.env["res.partner"]), "_dedup_merge", _dedup_merge, create=True
        ):
            group.action_merge()

        self.assertEqual(calls, [(master.id, [source.id])], "the hook must be used")
        self.assertEqual(group.state, "merged")
        self.assertTrue(
            source.active,
            "the model owns disposal; the generic path must not archive behind it",
        )
