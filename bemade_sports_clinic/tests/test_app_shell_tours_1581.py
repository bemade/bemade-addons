"""Task 1581 — histories in a browser (static/tests/tours/sc_app_history_tours.js).
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-HT1 (phone) Team announcement: the green « History » link in the section
  header opens the sheet; an announcement published from the page (no
  reload) is listed when the sheet opens again — fetched on every open.
* UC-HT2 (phone) Injury notes: « History » next to the External Notes label
  opens the sheet; the « Internal » chip re-fetches it with only internal
  entries; an external note saved on the page (autosave, no reload) is
  listed when the sheet opens again.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_history_1581 import History1581Common


@tagged('post_install', '-at_install')
class TestAppShellToursPhone1581(History1581Common):
    browser_size = '390x844'

    def test_announcement_fresh(self):
        self.start_tour(self.team_url, 'sc_1581_announcement_fresh', login='pc.tp@example.com')
        self.team_a.invalidate_recordset()
        self.assertEqual(self.team_a.announcement, 'Tour 1581 synthetic announcement')

    def test_notes_fresh(self):
        self.start_tour('/my/injury/edit?injury_id=%s&team_id=%s' % (self.injury.id, self.team_a.id),
                        'sc_1581_notes_fresh', login='pc.tp@example.com')
