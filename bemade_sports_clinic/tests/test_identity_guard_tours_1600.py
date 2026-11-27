"""Task 1600 — the identity confirmation in a browser
(static/tests/tours/sc_identity_guard_tours.js). Synthetic fixtures only.

Acceptance criteria covered:

* UC-T1 (phone, app shell OFF) Legacy edit form: correcting the first name
  and unticking a team shows the confirm step (old → new, the team to
  leave); « Back to the form » sends nothing; « Confirm and save » saves —
  the name is changed with the audit note, the team removal is the official
  one (flag cleared, note).
* UC-T2 (phone, app shell ON) Player page pencil: correcting the last name
  shows the banner (old → new) and saves nothing; « Cancel » restores the
  saved value; « Confirm » saves and records the note.

Visual layout (both themes, laptop width) stays for the dev-review
click-through.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_identity_guard_1600 import SWITCH, IdentityCommon


@tagged('post_install', '-at_install')
class TestIdentityGuardTours1600(IdentityCommon):
    browser_size = '390x844'


    def test_pencil_confirm_tour(self):
        self.env['ir.config_parameter'].sudo().set_param(SWITCH, 'True')
        self.start_tour('/my/player?player_id=%s&tab=info' % self.player.id,
                        'sc_1600_pencil_confirm', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.last_name, 'Onesynth')
        self.assertEqual(len(self._notes(self.player)), 1)
