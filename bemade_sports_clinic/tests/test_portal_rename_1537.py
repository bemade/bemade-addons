"""Task 1537 — a portal coach (or portal therapist) renaming a player must
not fail on the mirrored ``res.partner`` name write.

Background: ``sports.patient.write`` -> ``_recompute_name()`` mirrors
« First Last » onto the player's contact. Core ``res.partner.write`` then,
on a name change, loops ``partner.bank_ids`` to keep ``acc_holder_name`` in
sync — which a portal user cannot read (no ACL on ``res.partner.bank``) ->
AccessError « Bank Accounts », the contact name stayed stale and the portal
bounced back to the edit form with an error flash.

Acceptance criteria covered (synthetic fixtures — this addon's repository is
public):

* AC1 a portal coach renames a player, via the ORM and via POST
  ``/my/player/save``: no error, 303 to the player page (not the edit
  form), the contact name and ``_portal_list_name()`` carry the new name;
* AC2 same for a portal therapist (whose form also re-posts ``team_ids``);
* AC3 the bank-account holder name follows the rename when it matched the
  old name (the core sync path really runs, now as sudo);
* AC4 renaming a player's contact directly (no ``patient_update`` context)
  is still blocked by the ValidationError guard.

NOT claimed: the real browser click-through as a coach (dev-review UAT).
"""
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestPortalRename1537(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The player's contact carries a bank account whose holder name is the
        # player's current name, so core's rename sync reads bank_ids.
        cls.bank = cls.env['res.partner.bank'].create({
            'partner_id': cls.player.partner_id.id,
            'acc_number': 'TEST-1537-0001',
            'acc_holder_name': cls.player.partner_id.name,
        })
        cls.internal_tp = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Internal TP 1537', 'login': 'pc.internal.tp.1537@example.com',
            'group_ids': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('bemade_sports_clinic.group_sports_clinic_user').id,
                cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id,
            ])],
        })

    def _assert_renamed(self, first, last):
        partner = self.player.partner_id
        self.player.invalidate_recordset()
        partner.invalidate_recordset()
        self.bank.invalidate_recordset()
        self.assertEqual(self.player.first_name, first)
        self.assertEqual(self.player.last_name, last)
        self.assertEqual(partner.name, '%s %s' % (first, last),
                         "the contact name must mirror the new player name")
        self.assertEqual(self.player._portal_list_name(), '%s, %s' % (last, first))
        self.assertEqual(self.bank.acc_holder_name, '%s %s' % (first, last),
                         "the matching bank-account holder name follows the rename")

    def _assert_player_page_redirect(self, resp):
        self.assertEqual(resp.status_code, 303, resp.text[:500])
        location = resp.headers.get('Location', '')
        self.assertIn('/my/player?player_id=%s' % self.player.id, location)
        self.assertNotIn('/my/player/edit', location,
                         "a successful save must not bounce back to the edit form")

    # ----- AC1 / AC3: portal coach -----

    def test_coach_rename_orm(self):
        self.player.with_user(self.coach).write({'first_name': 'Renamed'})
        self._assert_renamed('Renamed', 'One')

    def test_coach_rename_portal_post(self):
        self._login_coach()
        resp = self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(),
            'patient_id': self.player.id,
            'first_name': 'Coachfirst', 'last_name': 'Coachlast',
        }, allow_redirects=False)
        self._assert_player_page_redirect(resp)
        self._assert_renamed('Coachfirst', 'Coachlast')

    # ----- AC2 / AC3: portal therapist -----

    def test_tp_rename_orm(self):
        self.player.with_user(self.tp).write({'first_name': 'Tpfirst'})
        self._assert_renamed('Tpfirst', 'One')

    def test_tp_rename_portal_post(self):
        self._login_tp()
        resp = self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(),
            'patient_id': self.player.id,
            'first_name': 'Tpfirst', 'last_name': 'Tplast',
            # The TP edit form re-posts the team selection.
            'team_ids': self.team_a.id,
        }, allow_redirects=False)
        self._assert_player_page_redirect(resp)
        self._assert_renamed('Tpfirst', 'Tplast')
        self.assertIn(self.team_a, self.player.team_ids)

    # ----- AC4: the direct-rename guard is intact -----

    @mute_logger('odoo.http')
    def test_direct_partner_rename_still_guarded(self):
        partner = self.player.partner_id
        with self.assertRaises(ValidationError):
            partner.with_user(self.internal_tp).write({'name': 'X'})
        partner.invalidate_recordset()
        self.assertEqual(partner.name, 'Pat One')
