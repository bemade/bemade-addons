"""Task 1582 — browser tour of the injury notes' « replace » editor
(static/tests/tours/sc_note_replace_tours.js), a therapist on a laptop
(1366 px) and a coach at phone width (390 px). Synthetic fixtures only.

Acceptance criteria covered here:

* UC-T1 Editing an existing external note opens an EMPTY « New note » editor
  under the read-only current text.
* UC-T2 An emptied editor left as is saves nothing (no history row, the text
  is untouched).
* UC-T3 « Reuse current text » prefills the editor with the current text.
* UC-T4 Saving replaces the text and adds EXACTLY one history row; the read
  view and the « current text » block show it without a reload, the editor
  is empty again.
* UC-T5 « History » on the field opens the external-scoped history sheet,
  which keeps the previous text.

Visual layout, both widths side by side and the French wording stay
UNVERIFIED here — the dev-review click-through covers them.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

CURRENT = 'T1582 tour current text'
NEW = 'T1582 tour replaced text'


class _Tour1582Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')
        cls.injury.sudo().write({'external_notes': CURRENT})

    def _run(self, login):
        History = self.env['sports.injury.note.history']
        domain = [('injury_id', '=', self.injury.id), ('scope', '=', 'external')]
        before = History.search_count(domain)
        self.start_tour('/my/injury/edit?injury_id=%s' % self.injury.id,
                        'sc_1582_note_replace', login=login)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, NEW)
        # The emptied editor saved nothing: the replacement is the ONLY row.
        self.assertEqual(History.search_count(domain), before + 1)
        self.assertEqual(History.search(domain, order='id desc', limit=1).content, NEW)


@tagged('post_install', '-at_install')
class TestNoteReplaceTourLaptop1582(_Tour1582Common):
    browser_size = '1366x768'

    def test_note_replace_therapist_laptop(self):
        self._run('pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestNoteReplaceTourPhone1582(_Tour1582Common):
    browser_size = '390x844'

    def test_note_replace_coach_phone(self):
        self._run('pc.coach@example.com')
