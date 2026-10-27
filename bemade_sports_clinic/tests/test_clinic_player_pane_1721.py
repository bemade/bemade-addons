"""Task 1721 — Clinique: the Dossier pane is the team page's player card,
the player form's injuries (resolved folded) and the clinical notes.
Synthetic fixtures only.

Acceptance criteria:

* AC-1 Top of the pane: the team page's expandable player card
  (``sc_player_row``) for the selected patient — status dot, Match /
  Pratique quick-change pills for a status editor, « Details » expander —
  with its own fragment key (``row-clinic``); the former hero and status
  card are gone (the medical pills stay under the card).
* AC-2 Injuries: the « + Ajouter » (the inline add panel) above the list;
  the active / unverified injuries in the player form's order (newest
  first); the resolved ones are NOT shown, behind « Show resolved injuries
  (N) » at the bottom (folded, only when N > 0).
* AC-3 No active injury: « No active injuries. », plus the resolved link
  when there are some, plus the Add control.
* AC-4 Clinical notes: unchanged (still saving — the 1590 / 1540 suites).
* AC-5 French: « Afficher les blessures résolues (N) », « Aucune blessure
  active. ».
* AC-6 Browser (laptop + phone): the resolved injuries fold out and back;
  « + Ajouter » opens the add panel.
"""
from datetime import date

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_clinic_dossier_inline_1590 import ClinicDossier1590Common


class Pane1721Common(ClinicDossier1590Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Injury = cls.env['sports.patient.injury']
        cls.inj_new = Injury.create({'patient_id': cls.player.id, 'diagnosis': 'Synthetic newer sprain',
                                     'injury_date': date(2026, 3, 2)})
        cls.inj_new.with_context(mail_notrack=True).write({'stage': 'active'})
        cls.inj_old = Injury.create({'patient_id': cls.player.id, 'diagnosis': 'Synthetic old knee',
                                     'injury_date': date(2025, 1, 5)})
        cls.inj_old.with_context(mail_notrack=True).write({'stage': 'resolved'})

    def _pane(self):
        _text, tree = self._get(self._dossier_url())
        return tree.xpath('//*[@data-sc-section="clinic.dossier"]')[0]


@tagged('post_install', '-at_install')
class TestClinicPlayerPane1721(Pane1721Common):

    def test_player_card_on_top(self):
        self._login_tp()
        pane = self._pane()
        card = pane.xpath('.//*[@data-sc-section="clinic.dossier.player"]//div[contains(@class, "o_sc_player_row")]')
        self.assertEqual(len(card), 1)
        self.assertEqual(card[0].get('data-sc-player-id'), str(self.player.id))
        self.assertTrue(card[0].xpath('.//*[@data-sc-fragment="sports.patient:%s:row-clinic"]' % self.player.id))
        self.assertTrue(card[0].xpath('.//button[@data-sc-row-expand]'))
        self.assertFalse(pane.xpath('.//*[@data-sc-section="clinic.dossier.status"]'))
        self.assertFalse(pane.xpath('.//*[@data-sc-action="clinic.full_file"]'))
        # The card comes first, the injuries after it, the notes last.
        sections = [el.get('data-sc-section') for el in pane.xpath(
            './/*[@data-sc-section="clinic.dossier.player" or @data-sc-section="clinic.dossier.injuries"'
            ' or @data-sc-section="clinic.dossier.notes"]')]
        self.assertEqual(sections, ['clinic.dossier.player', 'clinic.dossier.injuries', 'clinic.dossier.notes'])

    def test_injuries_resolved_folded(self):
        self._login_tp()
        pane = self._pane()
        section = pane.xpath('.//*[@data-sc-section="clinic.dossier.injuries"]')[0]
        self.assertTrue(section.xpath('.//button[@data-sc-list-add-toggle][@aria-controls="sc_clinic_injury_add"]'))
        active = section.xpath('.//*[@data-sc-section="clinic.dossier.injury_list"]')[0]
        self.assertIn('Synthetic newer sprain', active.text_content())
        self.assertNotIn('Synthetic old knee', active.text_content())
        folded = section.xpath('.//details[@data-sc-resolved-injuries]')
        self.assertEqual(len(folded), 1)
        self.assertIsNone(folded[0].get('open'))
        self.assertEqual(folded[0].xpath('./summary')[0].text_content().strip(), 'Show resolved injuries (1)')
        self.assertIn('Synthetic old knee', folded[0].text_content())
        # The resolved block comes after the active list.
        self.assertIs(folded[0].getparent().getprevious(), active)

    def _resolve_all(self):
        self.player.injury_ids.filtered(lambda i: i.stage != 'resolved').with_context(
            mail_notrack=True).write({'stage': 'resolved'})

    def test_no_active_injury(self):
        self._resolve_all()
        count = len(self.player.injury_ids)
        self._login_tp()
        section = self._pane().xpath('.//*[@data-sc-section="clinic.dossier.injuries"]')[0]
        self.assertEqual(section.xpath('.//*[@data-sc-section="clinic.dossier.no_active"]')[0].text_content().strip(),
                         'No active injuries.')
        self.assertEqual(section.xpath('.//details[@data-sc-resolved-injuries]/summary')[0].text_content().strip(),
                         'Show resolved injuries (%s)' % count)
        self.assertTrue(section.xpath('.//button[@data-sc-list-add-toggle]'))
        # No resolved one: no link.
        self.player.injury_ids.unlink()
        section = self._pane().xpath('.//*[@data-sc-section="clinic.dossier.injuries"]')[0]
        self.assertFalse(section.xpath('.//details[@data-sc-resolved-injuries]'))
        self.assertTrue(section.xpath('.//*[@data-sc-section="clinic.dossier.resolved"]'))

    def test_french(self):
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
                website.default_lang_id = fr_lang
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        self.tp.write({'lang': 'fr_CA'})
        self._login_tp()
        pane = self._pane()
        self.assertEqual(pane.xpath('.//details[@data-sc-resolved-injuries]/summary')[0].text_content().strip(),
                         'Afficher les blessures résolues (1)')
        self._resolve_all()
        pane = self._pane()
        self.assertEqual(pane.xpath('.//*[@data-sc-section="clinic.dossier.no_active"]')[0].text_content().strip(),
                         'Aucune blessure active.')


class _Tours1721:

    def test_resolved_fold_and_add(self):
        self._switch(True)
        self.start_tour(self._dossier_url(), 'sc_1721_clinic_pane', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestClinicPlayerPanePhone1721(_Tours1721, Pane1721Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestClinicPlayerPaneLaptop1721(_Tours1721, Pane1721Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
