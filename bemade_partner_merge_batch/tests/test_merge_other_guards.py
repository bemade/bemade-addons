"""Use case 5 - other modules' merge guards still hold across batches.

Acceptance criteria:
- When bemade_sports_clinic is installed, a merge of more than 3 contacts in
  which two contacts belong to different players (sports.patient) placed in
  different batches is refused, and nothing is merged: that module's guard
  runs on every batch and the batches accumulate into the kept contact.
- Skipped when bemade_sports_clinic is not installed.
"""
import unittest

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PartnerMergeBatchCase


@tagged("post_install", "-at_install")
class TestMergeOtherGuards(PartnerMergeBatchCase):

    def test_two_players_in_different_batches_refused(self):
        if "sports.patient" not in self.env:
            raise unittest.SkipTest("bemade_sports_clinic is not installed")
        Patient = self.env["sports.patient"]
        player_1 = Patient.create({"first_name": "Alpha", "last_name": "Sampleton"})
        player_2 = Patient.create({"first_name": "Omega", "last_name": "Sampleton"})
        others = self._make_partners(4)
        # dst first, then batches (others[1], player_1) (others[2], others[3])
        # (player_2): the two players never share a batch.
        partners = (
            others[0] + others[1] + player_1.partner_id
            + others[2] + others[3] + player_2.partner_id
        )
        with self.assertRaises(UserError) as cm:
            self._merge(partners, dst=others[0])
        self.assertIn("more than one player", str(cm.exception))
        self._assert_untouched(partners)
        self.env.invalidate_all()
        self.assertEqual(
            (player_1 + player_2).exists().mapped("partner_id"),
            player_1.partner_id + player_2.partner_id,
        )
