"""Acceptance criteria: the shipped contact target.

1.  Installing the module creates a target on ``res.partner`` pointing at
    ``dedup_key``, and its trigram index exists.
2.  Contacts under the SAME parent are deduplicated against each other;
    contacts under DIFFERENT parents never are, however identical their
    names. Child contacts are routinely named for a role -- "Accounts
    Payable", "Reception" -- and every company has one, so comparing across
    parents would collapse hundreds of unrelated people into one group. The
    engine enforces this in SQL, so the target does not need to exclude
    children to be safe.
3.  End to end: two partners differing only by a legal suffix are proposed as
    a group; merging them reassigns their attachments to the master and
    archives the source.
4.  Two partners with genuinely unrelated names are not proposed.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPartnerTarget(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target = cls.env.ref("bemade_fuzzy_dedup_partner.dedup_target_partner_name")

    def _groups_containing(self, *partners):
        wanted = {p.id for p in partners}
        return [
            group
            for group in self.target.group_ids
            if wanted <= set(group.record_ids.mapped("res_id"))
        ]

    def test_01_target_shipped_and_indexed(self):
        self.assertEqual(self.target.model_name, "res.partner")
        self.assertEqual(self.target.field_name, "dedup_key")
        self.assertTrue(self.target.index_name)
        self.env.cr.execute(
            "SELECT 1 FROM pg_indexes WHERE indexname = %s", (self.target.index_name,)
        )
        self.assertTrue(self.env.cr.rowcount, "the trigram index is missing")

    def test_02_siblings_deduped_but_never_across_parents(self):
        Partner = self.env["res.partner"]
        alpha = Partner.create({"name": "Alpha Foundation", "is_company": True})
        beta = Partner.create({"name": "Beta Foundation", "is_company": True})
        ap_alpha = Partner.create(
            {"name": "Accounts Payable", "parent_id": alpha.id}
        )
        ap_alpha_dup = Partner.create(
            {"name": "Accounts Payble", "parent_id": alpha.id}
        )
        ap_beta = Partner.create({"name": "Accounts Payable", "parent_id": beta.id})
        self.target._scan()
        self.assertTrue(
            self._groups_containing(ap_alpha, ap_alpha_dup),
            "duplicate contacts under one parent must be proposed",
        )
        self.assertFalse(
            self._groups_containing(ap_alpha, ap_beta),
            "the same role name under two parents is two different people",
        )

    def test_03_legal_suffix_duplicates_merge_end_to_end(self):
        Partner = self.env["res.partner"]
        master = Partner.create({"name": "Kestrel Instruments"})
        source = Partner.create({"name": "Kestrel Instruments Inc."})
        attachment = self.env["ir.attachment"].create(
            {"name": "quote.pdf", "res_model": "res.partner", "res_id": source.id}
        )
        self.target._scan()
        groups = self._groups_containing(master, source)
        self.assertEqual(len(groups), 1, "the pair was not proposed")
        groups[0].action_merge()
        self.assertEqual(attachment.res_id, master.id)
        self.assertFalse(source.active)
        self.assertTrue(master.active)

    def test_04_unrelated_names_not_proposed(self):
        Partner = self.env["res.partner"]
        a = Partner.create({"name": "Kestrel Instruments"})
        b = Partner.create({"name": "Vantage Logistics Group"})
        self.target._scan()
        self.assertFalse(self._groups_containing(a, b))
