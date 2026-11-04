"""Adversarial review 2026-10-22 — a player's injuries and contacts can't be
moved onto another player by a portal user. Synthetic fixtures only.

Acceptance criteria:

* OG-1 A portal therapist writing ``patient_id`` = another team's player on
  an injury of their own player is refused (AccessError); the injury stays
  on its player.
* OG-2 Same for an emergency contact.
* OG-3 Writing the SAME player back, and any other field, still works.
* OG-4 The superuser (the Merge Players wizard, data cleaning merges,
  migrations) still re-parents them.
"""
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.portal_cov_common import PortalCovCommon


@tagged('post_install', '-at_install')
class TestPatientOwnerGuard(PortalCovCommon):

    def test_injury_cannot_move_to_another_player(self):
        injury = self.injury.with_user(self.tp)
        with self.assertRaises(AccessError):
            injury.write({'patient_id': self.player_b.id})
        with self.assertRaises(AccessError):
            injury.write({'patient_id': False})
        self.assertEqual(self.injury.sudo().patient_id, self.player)
        # OG-3
        injury.write({'patient_id': self.player.id, 'diagnosis': 'Synthetic sprain'})
        self.assertEqual(self.injury.sudo().diagnosis, 'Synthetic sprain')

    def test_injury_created_then_moved_refused(self):
        injury = self.env['sports.patient.injury'].with_user(self.tp).create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic planted'})
        with self.assertRaises(AccessError):
            injury.write({'patient_id': self.player_b.id})
        self.assertFalse(self.env['sports.patient.injury'].sudo().search_count(
            [('patient_id', '=', self.player_b.id), ('diagnosis', '=', 'Synthetic planted')]))

    def test_contact_cannot_move_to_another_player(self):
        for user in (self.tp, self.coach):
            contact = self.contact.with_user(user)
            with self.assertRaises(AccessError):
                contact.write({'patient_id': self.player_b.id})
            self.assertEqual(self.contact.sudo().patient_id, self.player)
        self.contact.with_user(self.tp).write({'patient_id': self.player.id, 'name': 'Synthetic Parent'})
        self.assertEqual(self.contact.sudo().name, 'Synthetic Parent')

    def test_superuser_still_reparents(self):
        other = self.env['sports.patient'].create({'first_name': 'Synthetic', 'last_name': 'Dest'})
        other.team_ids = [Command.set([self.team_a.id])]
        self.injury.sudo().write({'patient_id': other.id})
        self.contact.sudo().write({'patient_id': other.id})
        self.assertEqual((self.injury.patient_id, self.contact.patient_id), (other, other))
