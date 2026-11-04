"""Task 1627 — the player page header and the clinic dossier: the Match and
Practice pills are coloured pill dropdowns (two clicks to change, outside the
pencil); the computed stage pill and the 4-way status changer are gone.
Synthetic fixtures only.

Acceptance criteria:

* AC-1 Player page header: no computed stage pill (« Blessé(e) » /
  « Pratiques autorisées » / « Matchs autorisés », ``data-sc-stage-chip``),
  for therapists and coaches.
* AC-2 Therapist: the Match and Practice pills are two
  ``button.o_sc_pill_select`` (``aria-haspopup="menu"``) coloured by value —
  Oui = green, Oui sans contact = yellow, Non = red (the player rows' tones)
  — each opening a ``role="menu"`` of ``menuitemradio`` items (the current
  one ``aria-checked``).
* AC-3 Coach: the same coloured pills, read-only: plain ``span`` pills, no
  button, no menu.
* AC-4 Invalid choices are greyed out with a hint (no auto-adjust): only the
  pairs yes:yes, no:yes, no:no_contact, no:no are valid. In the Match menu
  « Oui » is disabled unless Practice is « Oui »; in the Practice menu
  « Oui sans contact » and « Non » are disabled while Match is « Oui ». A
  disabled item carries ``aria-disabled`` and a visible hint, and posts
  nothing; every enabled item posts a VALID ``sc_status`` pair.
* AC-5 The pencil no longer holds a status changer: no ``sc_status``
  autosave field anywhere on the player page, no ``player.status.edit``
  section.
* AC-6 Clinic dossier: the same two pills replace the 4-way changer
  (therapists: dropdowns; the training recommendation stays live).
* AC-7 In-place refresh: the pills (with the ``write_date`` / ``old_value``
  the next change posts) sit inside the ``status`` read fragment, on both
  pages; a ``sc_status`` save refreshes ``status`` and ``predicted-return``,
  whose fresh render shows the new colours and the flipped return line.
* AC-8 French: « Match : Oui », « Pratique : Oui, sans contact », the hints
  (« Exige Pratique : Oui », « Mettre d'abord Match à Non »).
* AC-9 (browser, tour ``sc_1627_status_pills``): as a therapist, open the
  Practice pill (items greyed while Match = Oui), Match -> Non then
  Practice -> Non (pills recolour red in place, « Retour prévu » shows, no
  reload, no 409 on the second change), « Annuler » restores the previous
  pair, Practice -> Oui then Match -> Oui (green, « Retour réel »); the
  same change on the clinic dossier; as a coach, no button on the pills.
"""
from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon, FragmentsMixin
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common

PAIRS = ('yes:yes', 'no:yes', 'no:no_contact', 'no:no')
TONES = {'yes': 'green', 'no_contact': 'yellow', 'no': 'red'}


def _pills(node):
    """{key: pill node} of the status pills under ``node``."""
    return {pill.get('data-sc-pill-key'): pill
            for pill in node.xpath('.//*[@data-sc-pill-key]')}


def _items(tree, pill):
    """{value: item} of a dropdown pill's menu."""
    toggle = pill.xpath('.//button[contains(@class, "o_sc_pill_select")]')[0]
    popup = tree.xpath('//*[@id="%s"]' % toggle.get('aria-controls'))[0]
    return popup, {item.get('data-sc-pill-value'): item
                   for item in popup.xpath('.//*[@role="menuitemradio"]')}


class StatusPillsMixin(FragmentsMixin):

    def _set(self, pair):
        match, practice = pair.split(':')
        self.player.sudo().write({'match_status': match, 'practice_status': practice})
        self.player.invalidate_recordset()

    def _key(self, part):
        return 'sports.patient:%s:%s' % (self.player.id, part)

    def _status_node(self, tree):
        node = self._node(tree, self._key('status'))
        self.assertIsNotNone(node, 'no status fragment')
        return node

    def _assert_dropdowns(self, tree, pair):
        """Two coloured dropdown pills with the right items for ``pair``."""
        match, practice = pair.split(':')
        node = self._status_node(tree)
        pills = _pills(node)
        self.assertEqual(sorted(pills), ['match', 'practice'])
        for key, value in (('match', match), ('practice', practice)):
            buttons = pills[key].xpath('.//button[contains(@class, "o_sc_pill_select")]')
            self.assertEqual(len(buttons), 1, key)
            button = buttons[0]
            self.assertEqual(button.get('aria-haspopup'), 'menu')
            self.assertEqual(button.get('aria-expanded'), 'false')
            self.assertIn('o_sc_status_pill', button.get('class'))
            self.assertIn('o_sc_chip_%s' % TONES[value], button.get('class'), (key, pair))
            popup, items = _items(tree, pills[key])
            self.assertEqual(popup.get('role'), 'menu')
            self.assertEqual(popup.get('hidden'), 'hidden')
            checked = [v for v, item in items.items() if item.get('aria-checked') == 'true']
            self.assertEqual(checked, [value], (key, pair))
        return pills

    def _menu_state(self, tree):
        """{key: {value: post or None (disabled)}} of the two menus."""
        pills = _pills(self._status_node(tree))
        state = {}
        for key, pill in pills.items():
            _popup, items = _items(tree, pill)
            state[key] = {}
            for value, item in items.items():
                disabled = item.get('aria-disabled') == 'true'
                hint = ' '.join(item.xpath('.//*[contains(@class, "o_sc_pill_hint")]//text()')).strip()
                if disabled:
                    self.assertTrue(hint, 'a greyed choice says why (%s %s)' % (key, value))
                    self.assertFalse(item.get('data-sc-pill-post'))
                    state[key][value] = None
                else:
                    self.assertFalse(hint, (key, value))
                    state[key][value] = item.get('data-sc-pill-post')
        return state


@tagged('post_install', '-at_install')
class TestStatusPills1627(StatusPillsMixin, FragmentsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.sudo().write({'match_status': 'yes', 'practice_status': 'yes',
                                 'predicted_return_date': '2030-02-01', 'return_date': '2029-12-01'})

    def _url(self, tab='injuries'):
        return '/my/player?player_id=%s&tab=%s&team_id=%s' % (self.player.id, tab, self.team_a.id)

    @staticmethod
    def _hero(tree):
        return tree.xpath('//*[@data-sc-section="player.hero"]')[0]

    # -- AC-1 --------------------------------------------------------------
    def test_no_stage_chip(self):
        for login in (self._login_tp, self._login_coach):
            login()
            for pair in ('yes:yes', 'no:no'):
                self._set(pair)
                tree = self._page(self._url())
                self.assertFalse(tree.xpath('//*[@data-sc-stage-chip]'), pair)

    # -- AC-2 --------------------------------------------------------------
    def test_therapist_dropdown_pills(self):
        self._login_tp()
        for pair in PAIRS:
            self._set(pair)
            tree = self._page(self._url())
            pills = self._assert_dropdowns(tree, pair)
            # In the header's READ view (always live, never behind the pencil).
            for pill in pills.values():
                self.assertTrue(pill.xpath('ancestor::*[@data-sc-edit-view="read"]'))
                self.assertFalse(pill.xpath('ancestor::*[@data-sc-edit-view="edit"]'))

    # -- AC-3 --------------------------------------------------------------
    def test_coach_reads_coloured_pills(self):
        self._login_coach()
        for pair in PAIRS:
            self._set(pair)
            tree = self._page(self._url())
            node = self._status_node(tree)
            pills = _pills(node)
            self.assertEqual(sorted(pills), ['match', 'practice'])
            self.assertFalse(node.xpath('.//button'))
            self.assertFalse(tree.xpath('//*[contains(@class, "o_sc_pill_popup")]'))
            match, practice = pair.split(':')
            for key, value in (('match', match), ('practice', practice)):
                self.assertEqual(pills[key].tag, 'span')
                self.assertIn('o_sc_status_pill', pills[key].get('class'))
                self.assertIn('o_sc_chip_%s' % TONES[value], pills[key].get('class'), (key, pair))

    # -- AC-4 --------------------------------------------------------------
    def test_invalid_choices_greyed(self):
        self._login_tp()
        expected = {
            'yes:yes': {'match': {'yes': 'yes:yes', 'no': 'no:yes'},
                        'practice': {'yes': 'yes:yes', 'no_contact': None, 'no': None}},
            'no:yes': {'match': {'yes': 'yes:yes', 'no': 'no:yes'},
                       'practice': {'yes': 'no:yes', 'no_contact': 'no:no_contact', 'no': 'no:no'}},
            'no:no_contact': {'match': {'yes': None, 'no': 'no:no_contact'},
                              'practice': {'yes': 'no:yes', 'no_contact': 'no:no_contact', 'no': 'no:no'}},
            'no:no': {'match': {'yes': None, 'no': 'no:no'},
                      'practice': {'yes': 'no:yes', 'no_contact': 'no:no_contact', 'no': 'no:no'}},
        }
        for pair in PAIRS:
            self._set(pair)
            self.assertEqual(self._menu_state(self._page(self._url())), expected[pair], pair)

    def test_model_pills_never_offer_an_invalid_pair(self):
        """The model helper behind the component (unit level)."""
        valid = set(PAIRS)
        for pair in PAIRS:
            self._set(pair)
            pills = self.player._sc_status_pills()
            self.assertEqual([p['key'] for p in pills], ['match', 'practice'])
            for pill in pills:
                self.assertEqual(pill['target']['field'], 'sc_status')
                self.assertEqual(pill['target']['old_value'], pair)
                for option in pill['options']:
                    if option['disabled']:
                        self.assertTrue(option['hint'])
                        self.assertFalse(option['post'])
                    else:
                        self.assertIn(option['post'], valid, (pair, pill['key'], option['value']))

    # -- AC-5 --------------------------------------------------------------
    def test_no_status_changer_in_the_pencil(self):
        self._login_tp()
        tree = self._page(self._url())
        self.assertFalse(tree.xpath('//owl-component[contains(@props, \'"sc_status"\')]'))
        self.assertFalse(tree.xpath('//*[@data-sc-section="player.status.edit"]'))
        # The pencil stays for the header's other fields (training, dates; task 1630: the allergies are the pills' popups).
        hero = self._hero(tree)
        self.assertEqual(len(hero.xpath('.//button[@data-sc-edit-toggle]')), 1)

    # -- AC-7 --------------------------------------------------------------
    def test_pill_target_inside_the_status_fragment(self):
        self._login_tp()
        self._set('no:yes')
        tree = self._page(self._url())
        node = self._status_node(tree)
        wraps = node.xpath('.//*[@data-sc-pill-select]')
        self.assertEqual(len(wraps), 2)
        write_date = fields.Datetime.to_string(self.player.sudo().write_date)
        for wrap in wraps:
            self.assertEqual(wrap.get('data-sc-model'), 'sports.patient')
            self.assertEqual(wrap.get('data-sc-record-id'), str(self.player.id))
            self.assertEqual(wrap.get('data-sc-field'), 'sc_status')
            self.assertEqual(wrap.get('data-sc-write-date'), write_date)
            self.assertEqual(wrap.get('data-sc-old-value'), 'no:yes')
            self.assertTrue(wrap.get('data-sc-undo-message'))
        self.assertFragmentMatchesPage(self._url(), self._key('status'))

    def test_save_refreshes_pills_and_return_line(self):
        self._login_tp()
        payload = self._saved(self.player, 'sc_status', 'no:no')
        for part in ('status', 'predicted-return'):
            self.assertRefreshes(payload, self._key(part))
        status = self._fragment(self._url(), self._key('status'))
        for key, pill in _pills(status).items():
            button = pill.xpath('.//button[contains(@class, "o_sc_pill_select")]')[0]
            self.assertIn('o_sc_chip_red', button.get('class'), key)
        # The fresh fragment carries the write_date the NEXT change posts.
        self.player.invalidate_recordset()
        self.assertEqual(status.xpath('.//*[@data-sc-pill-select]/@data-sc-write-date')[0],
                         payload['write_date'])
        self.assertEqual(status.xpath('.//*[@data-sc-pill-select]/@data-sc-old-value')[0], 'no:no')
        ret = self._fragment(self._url(), self._key('predicted-return'))
        self.assertEqual(ret.get('data-sc-return-kind'), 'predicted')
        # A second change right after, from the fresh values: no 409.
        resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'sc_status', 'value': 'no:yes', 'write_date': payload['write_date'],
            'old_value': 'no:no', 'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = self._saved(self.player, 'sc_status', 'yes:yes')
        ret = self._fragment(self._url(), self._key('predicted-return'))
        self.assertEqual(ret.get('data-sc-return-kind'), 'actual')

    def test_coach_cannot_save_status(self):
        self._login_coach()
        self.assertEqual(self._save(self.player, 'sc_status', 'no:no').status_code, 403)

    def test_tour(self):
        self._set('yes:yes')
        self.start_tour(self._url(), 'sc_1627_status_pills', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status), ('yes', 'yes'))

    def test_tour_coach(self):
        self.start_tour(self._url(), 'sc_1627_status_pills_coach', login='pc.coach@example.com')


@tagged('post_install', '-at_install')
class TestStatusPillsFrench1627(StatusPillsMixin, FragmentsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        fr = env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr.id)]
        (cls.tp | cls.coach).write({'lang': 'fr_CA'})

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.text.replace('&#39;', "'")

    def _url(self):
        return '/my/player?player_id=%s&tab=injuries' % self.player.id

    def test_french_labels_and_hints(self):
        self._login_tp()
        self._set('yes:yes')
        text = self._fr(self._url())
        for term in ('Match : Oui', 'Pratique : Oui', "Mettre d'abord Match à Non", 'Oui, sans contact',
                     'Statut modifié'):
            self.assertIn(term, text)
        self.assertNotIn('Match:', text)
        self.assertNotIn('Practice:', text)
        self._set('no:no_contact')
        text = self._fr(self._url())
        for term in ('Match : Non', 'Pratique : Oui, sans contact', 'Exige Pratique : Oui'):
            self.assertIn(term, text)
        self._login_coach()
        text = self._fr(self._url())
        self.assertIn('Match : Non', text)
        self.assertIn('Pratique : Oui, sans contact', text)


@tagged('post_install', '-at_install')
class TestDossierStatusPills1627(StatusPillsMixin, Clinic1540Common):

    def setUp(self):
        super().setUp()
        self._switch(True)
        self._set('yes:yes')

    def _url(self):
        return '/my/clinic/%s?patient=%s&tab=dossier' % (self.clinic.id, self.player.id)

    # Task 1721: the dossier's pills are now the player card's (the team
    # page's row, fragment « row-clinic »), not a status card's.
    def _status_node(self, tree):
        node = self._node(tree, self._key('row-clinic'))
        self.assertIsNotNone(node, 'no player card fragment')
        return node

    # -- AC-6 --------------------------------------------------------------
    def test_dossier_pills_replace_the_changer(self):
        self._login_tp()
        tree = self._page(self._url())
        card = tree.xpath('//*[@data-sc-section="clinic.dossier.player"]')[0]
        self.assertFalse(card.xpath('.//owl-component'))
        self.assertFalse(tree.xpath('//owl-component[contains(@props, \'"sc_status"\')]'))
        status = self._status_node(tree)
        self.assertTrue(status.xpath('ancestor::*[@data-sc-section="clinic.dossier.player"]'))
        self._assert_dropdowns(tree, 'yes:yes')
        self.assertEqual(self._menu_state(tree)['practice'], {'yes': 'yes:yes', 'no_contact': None, 'no': None})

    # -- AC-7 --------------------------------------------------------------
    def test_dossier_save_refreshes_in_place(self):
        self._login_tp()
        payload = self._saved(self.player, 'sc_status', 'no:no_contact')
        self.assertRefreshes(payload, self._key('row-clinic'))
        status = self._fragment(self._url(), self._key('row-clinic'))
        classes = {key: pill.xpath('.//button')[0].get('class') for key, pill in _pills(status).items()}
        self.assertIn('o_sc_chip_red', classes['match'])
        self.assertIn('o_sc_chip_yellow', classes['practice'])
        self.assertFragmentMatchesPage(self._url(), self._key('row-clinic'))

    def test_dossier_tour(self):
        self.start_tour(self._url(), 'sc_1627_status_pills_dossier', login=self.tp.login)
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status), ('no', 'yes'))
