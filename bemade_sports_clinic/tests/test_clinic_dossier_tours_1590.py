"""Task 1590 — browser tours of the clinic dossier's inline injuries
(static/tests/tours/sc_clinic_dossier_tours.js), a portal therapist on a
laptop (both panes) and at phone width (file tab). Synthetic fixtures only.

Acceptance criteria covered here:

* UC-T1 From the clinic dossier, « Add Injury » → « Yes » → diagnosis →
  « Create » lands back on THE CLINIC page, same patient, file shown, the new
  injury open in edit mode.
* UC-T2 A quick note typed in that card saves in place (replace editor) and
  shows its « last note » stamp; « Done » reloads the same clinic / patient /
  file tab, the read view showing the note; the pencil reopens the edit view.
  The legacy injury form never appears.
* UC-T3 « Undo » of a create made from the dossier deletes it and returns to
  the dossier.

The live worklist polls on the same page throughout (Clinic1540Common's
clinic). Visual layout and the French wording stay UNVERIFIED here — the
dev-review click-through (during a real clinic window) covers them.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common

DIAG_EDIT = 'Tour 1590 synthetic shoulder'
DIAG_UNDO = 'Tour 1590 synthetic undo'
QUICK_NOTE = 'Tour 1590 synthetic current state'


class _Tour1590Common(Clinic1540Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')

    def _url(self):
        return '/my/clinic/%s?patient=%s&tab=dossier' % (self.clinic.id, self.player.id)

    def _injury(self, diagnosis):
        return self.env['sports.patient.injury'].search(
            [('patient_id', '=', self.player.id), ('diagnosis', '=', diagnosis)])

    def _run_edit(self):
        self.start_tour(self._url(), 'sc_1590_clinic_injury_edit', login='pc.tp@example.com')
        injury = self._injury(DIAG_EDIT)
        self.assertEqual(len(injury), 1)
        self.assertEqual(injury.external_notes, QUICK_NOTE)
        self.assertFalse(injury.hidden_from_coaches)

    def _run_undo(self):
        self.start_tour(self._url(), 'sc_1590_clinic_injury_undo', login='pc.tp@example.com')
        self.assertFalse(self._injury(DIAG_UNDO))


@tagged('post_install', '-at_install')
class TestClinicDossierTourLaptop1590(_Tour1590Common):
    browser_size = '1366x768'

    def test_clinic_injury_edit_laptop(self):
        self._run_edit()

    def test_clinic_injury_undo_laptop(self):
        self._run_undo()


@tagged('post_install', '-at_install')
class TestClinicDossierTourPhone1590(_Tour1590Common):
    browser_size = '390x844'

    def test_clinic_injury_edit_phone(self):
        self._run_edit()
