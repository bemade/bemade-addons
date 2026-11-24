"""Use case 1 - merge more than 3 contacts.

Acceptance criteria:
- Merging 5 (and 13) contacts sharing one email keeps exactly one contact and
  deletes all the others.
- Everything pointing at a merged contact (a child contact, a bank account, an
  attachment) now points at the kept contact.
- The kept contact is the one given as destination; without one it is the
  contact Odoo itself would keep (``_get_ordered_partner(...)[-1]``).
- Merging 2 or 3 contacts behaves exactly as standard Odoo.
"""
from odoo.tests import tagged

from .common import PartnerMergeBatchCase


@tagged("post_install", "-at_install")
class TestMergeMany(PartnerMergeBatchCase):

    def _merge_and_check(self, count):
        partners = self._make_partners(count)
        dst = partners[0]
        children = self.Partner.create([
            {"name": f"Child of {p.name}", "parent_id": p.id} for p in partners[1:]
        ])
        banks = self.env["res.partner.bank"].create([
            {"acc_number": f"BATCH-{i:04d}", "partner_id": p.id}
            for i, p in enumerate(partners[1:])
        ])
        attachments = self.env["ir.attachment"].create([
            {"name": f"doc {i}", "res_model": "res.partner", "res_id": p.id}
            for i, p in enumerate(partners[1:])
        ])

        self._merge(partners, dst=dst)

        self.assertEqual(partners.exists(), dst)
        self.assertEqual(set(children.mapped("parent_id").ids), {dst.id})
        self.assertEqual(set(banks.mapped("partner_id").ids), {dst.id})
        self.assertEqual(set(attachments.mapped("res_id")), {dst.id})

    def test_merge_five(self):
        self._merge_and_check(5)

    def test_merge_thirteen(self):
        self._merge_and_check(13)

    def test_default_destination_is_cores_choice(self):
        partners = self._make_partners(6)
        expected = self.Wizard._get_ordered_partner(partners.ids)[-1]
        self._merge(partners)
        self.assertEqual(partners.exists(), expected)

    def test_merge_three_still_core(self):
        partners = self._make_partners(3)
        self._merge(partners, dst=partners[2])
        self.assertEqual(partners.exists(), partners[2])

    def test_merge_two_still_core(self):
        partners = self._make_partners(2)
        self._merge(partners, dst=partners[0])
        self.assertEqual(partners.exists(), partners[0])
