"""Task 1616 — the injury card in three sections in a browser (phone 390 px
and laptop 1366 px). Synthetic fixtures only.

Acceptance criteria (static/tests/tours/sc_injury_card_1616_tours.js):

* AC-T1 The open card shows Details, Notes and Documents — on a laptop
  Notes to the right of Details and Documents under Details, on a phone
  stacked Details → Notes → Documents; each pencil opens its own group only;
  the card's « Done » closes the open groups and the card.
* AC-T2 « Add » in Documents: a file over 10 MB is flagged and nothing is
  posted; two small files with one category / description upload at once
  and come back to the open card listing both; one is then renamed in place
  (pencil, saved on leaving the field) and its row follows without a reload.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class CardToursCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.injury.write({'diagnosis': 'Synthetic ankle', 'external_notes': 'Synthetic external note'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _card_url(self):
        return '/my/player?player_id=%s&tab=injuries&injury=%s' % (self.player.id, self.injury.id)


class CardTours:

    def test_card_sections(self):
        self.start_tour(self._card_url(), 'sc_1616_card_sections', login='pc.tp@example.com')

    def test_documents_upload(self):
        self.start_tour(self._card_url(), 'sc_1616_documents_upload', login='pc.tp@example.com')
        docs = self.env['sports.injury.document'].search([('injury_id', '=', self.injury.id)])
        # Review fixes 2026-10-18: three files chosen in three goes (the big
        # one removed, a duplicate ignored), uploaded together; one renamed.
        names = docs.mapped('name')
        self.assertEqual(len(docs), 3, names)
        self.assertIn('Synthetic X-ray report', names)
        self.assertLessEqual(set(names) - {'Synthetic X-ray report'},
                             {'Synthetic small.pdf', 'Synthetic a.pdf', 'Synthetic b.pdf'})
        self.assertEqual(set(docs.mapped('category')), {'medical_imaging'})
        self.assertEqual(set(docs.mapped('description')), {'Synthetic batch'})
        self.assertNotIn('Synthetic big.pdf', docs.mapped('file_name'))


@tagged('post_install', '-at_install')
class TestInjuryCardToursPhone1616(CardTours, CardToursCommon):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestInjuryCardToursLaptop1616(CardTours, CardToursCommon):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
