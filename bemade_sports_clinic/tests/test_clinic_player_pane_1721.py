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

Review round 1 (owner UAT 2026-10-27):

* AC-7 One list fragment (``injury-lists``, list mode) holds the active
  cards, « No active injuries. » and the resolved fold-out with its count:
  a stage change refreshes them together (a resolved card set back to
  « Actif » joins the active list without a reload; browser: the tour).
* AC-8 The treatment-note « Link to an injury » picker matches the pane:
  the add form lists the active / unverified injuries only; editing a note
  lists them plus the note's own injury (« (resolved) » if it is). The
  player page keeps every injury (its list shows them all, #1665).
* AC-9 A note card's pencil / ✓ sits in the card's head (top right, the
  meta line), not in the body.
* AC-10 The page uses the full width on a laptop (``o_sc_content_wide``).
* AC-11 (owner decision, app-wide) the Allergies / Medical alert pills are
  inside the player card — its own line right under Match / Practice —
  even when empty (grey); no separate pills under the card.
"""
import json
from datetime import date

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsMixin
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
        # AC-7: one list fragment holds both lists (and the count).
        lists = section.xpath('.//*[@data-sc-fragment="sports.patient:%s:injury-lists"]' % self.player.id)
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].get('data-sc-fragment-mode'), 'list')
        self.assertIs(active.getparent(), lists[0])
        self.assertTrue(lists[0].xpath('.//details[@data-sc-resolved-injuries][@data-sc-keep-open]'))
        items = lists[0].xpath('.//*[@data-sc-fragment-item]/@data-sc-fragment-item')
        self.assertIn('sports.patient.injury:%s:card' % self.inj_old.id, items)
        self.assertIn('sports.patient.injury:%s:card' % self.inj_new.id, items)
        self.assertFalse(section.xpath('.//*[@data-sc-fragment="sports.patient:%s:active-injuries"]'
                                       % self.player.id))

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

    # -- AC-8 ------------------------------------------------------------
    def _note(self, injury):
        return self.env['sports.treatment.note'].create({
            'patient_id': self.player.id, 'injury_id': injury.id if injury else False,
            'note': 'Synthetic note 1721', 'user_id': self.tp.id,
        })

    def test_note_picker_matches_the_pane(self):
        note_old = self._note(self.inj_old)
        note_new = self._note(self.inj_new)
        self._login_tp()
        _text, tree = self._get(self._dossier_url())
        pane = tree.xpath('//*[@data-sc-section="clinic.dossier"]')[0]
        add = [o.text_content().strip() for o in pane.xpath('.//select[@id="sc_note_injury"]/option[@value!=""]')]
        self.assertIn('Synthetic newer sprain', add)
        self.assertNotIn('Synthetic old knee (resolved)', add)
        self.assertFalse([label for label in add if label.endswith('(resolved)')])
        props = {}
        for comp in pane.xpath('.//*[@data-sc-note-id]//owl-component'):
            data = json.loads(comp.get('props'))
            if data.get('field') == 'injury_id':
                props[int(comp.xpath('ancestor::*[@data-sc-note-id]')[0].get('data-sc-note-id'))] = [
                    opt[1] for opt in data['options'] if opt[0]]
        # Edit = the add list (+ the note's own resolved injury, last).
        self.assertEqual(props[note_new.id], add)
        self.assertEqual(props[note_old.id], add + ['Synthetic old knee (resolved)'])
        # The player page keeps every injury (its list shows them all).
        _text, tree = self._get('/my/player?player_id=%s&tab=notes' % self.player.id)
        full = [o.text_content().strip() for o in tree.xpath('//select[@id="sc_note_injury"]/option[@value!=""]')]
        self.assertEqual(full, add + ['Synthetic old knee (resolved)'])

    # -- AC-9 / AC-10 / AC-11 --------------------------------------------
    def test_note_head_width_and_card_pills(self):
        self._note(self.inj_new)
        self._login_tp()
        _text, tree = self._get(self._dossier_url())
        self.assertIn('o_sc_content_wide', tree.xpath('//main[@id="sc_content"]')[0].get('class'))
        card = tree.xpath('//*[@data-sc-section="clinic.dossier"]//*[@data-sc-note-id][@data-sc-edit-card]')[0]
        head = card.xpath('./div[contains(@class, "o_sc_note_head")]')[0]
        self.assertTrue(head.xpath('./button[@data-sc-edit-toggle]'))
        self.assertTrue(head.xpath('./*[contains(@class, "o_sc_note_meta")]'))
        self.assertFalse(card.xpath('.//*[contains(@class, "o_sc_note_body")]'))
        player = tree.xpath('//*[@data-sc-section="clinic.dossier.player"]')[0]
        line = player.xpath('.//*[@data-sc-row-med]')
        self.assertEqual(len(line), 1)
        self.assertEqual(line[0].xpath('./button/@data-sc-med-pill'), ['allergy', 'medical_alert'])
        # Right under the Match / Practice line, inside the card's fragment.
        self.assertIn('o_sc_row_status', line[0].getprevious().get('class'))
        self.assertTrue(line[0].xpath('ancestor::*[@data-sc-fragment="sports.patient:%s:row-clinic"]'
                                      % self.player.id))
        self.assertFalse(tree.xpath('//*[contains(@class, "o_sc_clinic_medical")]'))

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


@tagged('post_install', '-at_install')
class TestClinicPaneFragments1721(FragmentsMixin, Pane1721Common):

    # -- AC-7 ------------------------------------------------------------
    def test_stage_change_refreshes_both_lists(self):
        self._login_tp()
        key = 'sports.patient:%s:injury-lists' % self.player.id
        old_card = 'sports.patient.injury:%s:card' % self.inj_old.id
        payload = self._saved(self.inj_old, 'stage', 'active')
        self.assertRefreshes(payload, key)
        node = self._fragment(self._dossier_url(), key)
        active = node.xpath('.//*[@data-sc-section="clinic.dossier.injury_list"]'
                            '//*[@data-sc-fragment-item]/@data-sc-fragment-item')
        self.assertIn(old_card, active)
        # Nothing resolved any more: no fold-out (its count went with it).
        self.assertFalse(node.xpath('.//details[@data-sc-resolved-injuries]'))


class _Tours1721:

    def test_resolved_fold_and_add(self):
        self._switch(True)
        self.start_tour(self._dossier_url(), 'sc_1721_clinic_pane', login='pc.tp@example.com')

    def test_resolved_back_to_active(self):
        self._switch(True)
        self.start_tour(self._dossier_url(), 'sc_1721_resolved_back_to_active', login='pc.tp@example.com')
        self.assertEqual(self.inj_old.stage, 'active')

    def test_note_check_top_right(self):
        self.env['sports.treatment.note'].create({
            'patient_id': self.player.id, 'injury_id': self.inj_new.id,
            'note': 'Synthetic note 1721', 'user_id': self.tp.id,
        })
        self._switch(True)
        self.start_tour(self._dossier_url(), 'sc_1721_note_check_top_right', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestClinicPlayerPanePhone1721(_Tours1721, Pane1721Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestClinicPlayerPaneLaptop1721(_Tours1721, Pane1721Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'

    def test_split_widths(self):
        # Review round 2 (owner 2026-10-27): a fixed-width worklist, the
        # dossier takes the remaining width.
        self._switch(True)
        self.start_tour(self._dossier_url(), 'sc_1721_split_widths', login='pc.tp@example.com')
