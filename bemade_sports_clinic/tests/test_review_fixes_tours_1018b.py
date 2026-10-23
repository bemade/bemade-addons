"""Review fixes 2026-10-18 b — browser checks
(static/tests/tours/sc_review_fixes_1018b_tours.js). Synthetic fixtures.

* T-1 The player Documents tab's picker (the injury card's): files added
  in two goes add up (duplicate ignored); each row is pre-filled with the
  shared category / description when added, its own changes stay on that
  file (and survive a re-render); « × » drops one; the phone layout stacks
  a row; one upload stores each file's own name / category / description,
  linked to the chosen injury. Round 2 (1018c): the shared fields show
  only while no file is listed (hidden with a row, back once emptied).

The « Mon compte » cards are covered by sc_1620_account (rewritten for the
pencil cards). UI is UNVERIFIED until /dev-review clicks it.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class _Tours1018b:

    def test_player_documents(self):
        self._switch(True)
        self.start_tour('/my/player?player_id=%s&tab=documents' % self.player.id,
                        'sc_1018b_player_documents', login='pc.tp@example.com')
        docs = self.env['sports.injury.document'].search([('patient_id', '=', self.player.id)])
        got = {d.file_name: (d.name, d.category, d.description, d.injury_id) for d in docs}
        self.assertEqual(got, {
            'Synthetic a.pdf': ('Synthetic A report', 'medical_imaging', 'Synthetic only a', self.injury),
            'Synthetic b.pdf': ('Synthetic b.pdf', 'prescription', 'Synthetic shared one', self.injury),
        })


@tagged('post_install', '-at_install')
class TestReviewFixesToursPhone1018b(_Tours1018b, AppShellCommon):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestReviewFixesToursLaptop1018b(_Tours1018b, AppShellCommon):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
