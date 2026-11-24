"""Use case 4 - Data Cleaning > Duplicates > Merge on a group of 5+.

Acceptance criteria:
- When the (enterprise) Data Cleaning app is installed, merging a res.partner
  duplicate group of 5 contacts keeps only the group's master contact.
- Skipped when Data Cleaning is not installed (this module only depends on
  base).
"""
import unittest

from odoo.fields import Command
from odoo.tests import tagged

from .common import PartnerMergeBatchCase


@tagged("post_install", "-at_install")
class TestMergeDataCleaning(PartnerMergeBatchCase):

    def test_data_cleaning_group_of_five(self):
        if "data_merge.model" not in self.env:
            raise unittest.SkipTest("data_cleaning is not installed")
        partners = self._make_partners(5, email="dc.batch.dup@example.com")
        model = self.env["data_merge.model"].create({
            "name": "Batch merge test contacts",
            "res_model_id": self.env["ir.model"]._get("res.partner").id,
            "domain": f"[('id', 'in', {partners.ids})]",
            "rule_ids": [Command.create({
                "field_id": self.env["ir.model.fields"]._get("res.partner", "email").id,
                "match_mode": "exact",
            })],
        })
        model.find_duplicates()
        group = self.env["data_merge.group"].search([("model_id", "=", model.id)])
        self.assertEqual(len(group), 1)
        self.assertEqual(len(group.record_ids), 5)
        master = group.record_ids.filtered("is_master") or group.record_ids.sorted("id")[:1]
        kept = self.Partner.browse(master.res_id)

        group.merge_records()

        self.env.invalidate_all()
        self.assertEqual(partners.exists(), kept)
