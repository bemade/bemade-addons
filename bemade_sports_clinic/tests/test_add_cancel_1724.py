"""Task 1724 — inline add panels get « Annuler ». Synthetic fixtures only.

Acceptance criteria:

* AC-1 Every inline add panel opened from a list header
  (``details.o_sc_list_add_panel``: activity, emergency contact, injury,
  note, player add — team page and players list —, player request, medical
  list items) has a ``button[data-sc-list-add-cancel]`` « Cancel » next to
  its submit (type=button, never submits). Bottom-sheet adds (documents,
  timesheet, clinic patient) already had « Cancel » (sc_sheet).
* AC-2 Browser: « Annuler » closes the panel, clears its fields and its
  device draft, the focus goes back to « + Ajouter »; reopened, the panel
  is empty (activity panel + the note panel, phone and laptop).
* AC-3 French: « Annuler ».

The real taps stay UNVERIFIED until /dev-review.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_player_add_inline_1655 import PlayerAdd1655Common


@tagged('post_install', '-at_install')
class TestAddCancel1724(PlayerAdd1655Common):

    def _cancel_in(self, tree, panel_id):
        panels = tree.xpath('//details[@id="%s"]' % panel_id)
        self.assertEqual(len(panels), 1, panel_id)
        panel = panels[0]
        self.assertIn('o_sc_list_add_panel', panel.get('class'), panel_id)
        buttons = panel.xpath('.//form//*[contains(concat(" ", @class, " "), " o_sc_form_actions ")]'
                              '/button[@data-sc-list-add-cancel]')
        self.assertEqual(len(buttons), 1, panel_id)
        self.assertEqual(buttons[0].get('type'), 'button', panel_id)
        # Next to the submit.
        self.assertTrue(buttons[0].getparent().xpath('./button[@type="submit"]'), panel_id)
        return buttons[0]

    def test_every_add_panel_has_cancel(self):
        self._login_tp()
        player = '/my/player?player_id=%s' % self.player.id
        pages = {
            player + '&tab=activities': ['sc_activity_add'],
            player + '&tab=notes': ['sc_note_add'],
            player + '&tab=injuries': ['sc_new_injury'],
            player + '&tab=info': ['sc_contact_add'],
            '/my/team?team_id=%s&tab=players' % self.team_a.id: ['sc_add_player'],
            '/my/players?add=1': ['sc_player_add'],
        }
        for url, ids in pages.items():
            _text, tree = self._get(url)
            for panel_id in ids:
                button = self._cancel_in(tree, panel_id)
                self.assertEqual(' '.join(button.text_content().split()), 'Cancel')
        # Every header-toggled panel of the player info tab (medical lists
        # included) carries one.
        _text, tree = self._get(player + '&tab=info')
        panels = tree.xpath('//details[contains(concat(" ", @class, " "), " o_sc_list_add_panel ")]')
        self.assertTrue(panels)
        for panel in panels:
            self.assertEqual(len(panel.xpath('.//button[@data-sc-list-add-cancel]')), 1, panel.get('id'))

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
        _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        button = self._cancel_in(tree, 'sc_activity_add')
        self.assertEqual(' '.join(button.text_content().split()), 'Annuler')


class _Tours1724:

    def test_activity_cancel(self):
        self.start_tour('/my/player?player_id=%s&tab=activities' % self.player.id, 'sc_1724_activity_cancel',
                        login='pc.tp@example.com')

    def test_note_cancel(self):
        self.start_tour('/my/player?player_id=%s&tab=notes' % self.player.id, 'sc_1724_note_cancel',
                        login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestAddCancelPhone1724(_Tours1724, PlayerAdd1655Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestAddCancelLaptop1724(_Tours1724, PlayerAdd1655Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
