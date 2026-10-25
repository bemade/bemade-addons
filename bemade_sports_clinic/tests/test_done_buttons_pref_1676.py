"""Task 1676 — the edit cards' « Terminé » buttons are a per-user setting
(default hidden); in edit mode the head pencil is a ✓ that closes the card;
the injury card loses its bottom « Terminé » and gets « Supprimer la
blessure » on the left. Synthetic fixtures only.

Acceptance criteria:

* AC-1 ``res.users.sc_show_done_buttons`` defaults to False; Paramètres
  shows the « Show « Done » buttons » On / Off switch; /my/app/pref sets it
  on the caller's own record only (another user's id → 403, nothing
  written).
* AC-2 The app root carries ``data-sc-hide-done="1"`` while the setting is
  off (CSS hides every « Done »), not when it is on.
* AC-3 The injury card's foot has no « Done » (``injury.done``); a
  therapist gets « Delete injury » (``injury.delete``) opening the confirm
  sheet; a coach gets no foot at all.
* AC-4 fr_CA: « Afficher les boutons Terminé », « Supprimer la blessure »,
  the ✓'s « Terminer la modification » (the layout's label).
* AC-5 Browser (phone 390 px + laptop 1366 px), setting off (default): no
  visible « Done »; the pencil turns into a ✓ (« Finish editing ») in edit
  mode and the ✓ closes the card — a player info card and an injury note;
  the injury foot's « Delete injury » sits on the left and opens its
  confirm. Setting on: « Done » visible and closing as before.

The real iPhone rendering stays UNVERIFIED until /dev-review.
"""
from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class Done1676Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The task's default: hidden (the shared fixture shows them).
        (cls.coach | cls.tp).write({'sc_show_done_buttons': False})
        cls.injury.sudo().with_context(mail_notrack=True).write({
            'external_notes': 'Synthetic ext 1676', 'internal_notes': 'Synthetic int 1676'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _card_url(self):
        return '/my/player?player_id=%s&tab=injuries&injury=%s' % (self.player.id, self.injury.id)

    def _app(self, tree):
        return tree.xpath('//*[@data-sc-app-shell]')[0]


@tagged('post_install', '-at_install')
class TestDoneButtonsPref1676(Done1676Common):

    def test_default_is_hidden(self):
        user = self.env['res.users'].create({'name': 'Fresh 1676', 'login': 'fresh.1676@example.com'})
        self.assertFalse(user.sc_show_done_buttons)

    def test_setting_persists_own_user_only(self):
        self._login_tp()
        _text, tree = self._get('/my/app/settings')
        section = tree.xpath('//section[@data-sc-section="settings.done_buttons"]')[0]
        self.assertEqual(section.xpath('.//button[@value="0"]/@aria-pressed'), ['true'])
        self.assertEqual(self._app(tree).get('data-sc-hide-done'), '1')
        resp = self.url_open('/my/app/pref', data={'csrf_token': self._csrf(), 'sc_show_done_buttons': '1',
                                                   'redirect': '/my/app/settings'}, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.tp.invalidate_recordset()
        self.assertTrue(self.tp.sc_show_done_buttons)
        self.assertFalse(self.coach.sc_show_done_buttons)
        _text, tree = self._get('/my/app/settings')
        section = tree.xpath('//section[@data-sc-section="settings.done_buttons"]')[0]
        self.assertEqual(section.xpath('.//button[@value="1"]/@aria-pressed'), ['true'])
        self.assertIsNone(self._app(tree).get('data-sc-hide-done'))
        with mute_logger('odoo.http'):
            resp = self.url_open('/my/app/pref', data={'csrf_token': self._csrf(), 'sc_show_done_buttons': '1',
                                                       'user_id': self.coach.id}, allow_redirects=False)
        self.assertEqual(resp.status_code, 403)
        self.coach.invalidate_recordset()
        self.assertFalse(self.coach.sc_show_done_buttons)
        resp = self.url_open('/my/app/pref', data={'csrf_token': self._csrf(), 'sc_show_done_buttons': 'yes'},
                             allow_redirects=False)
        self.assertEqual(resp.status_code, 400)

    def test_injury_foot(self):
        self._login_tp()
        _text, tree = self._get(self._card_url())
        card = tree.xpath('//details[@id="injury-%s"]' % self.injury.id)[0]
        self.assertFalse(card.xpath('.//*[@data-sc-injury-done]'))
        self.assertFalse(card.xpath('.//*[@data-sc-action="injury.done"]'))
        foot = card.xpath('.//div[contains(@class, "o_sc_injury_card_actions")]')[0]
        buttons = foot.xpath('.//button')
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].get('data-sc-action'), 'injury.delete')
        self.assertEqual(' '.join(buttons[0].text_content().split()), 'Delete injury')
        self.assertIn('o_sc_btn_danger', buttons[0].get('class'))
        self.assertEqual(buttons[0].get('data-sc-sheet-open'), 'sc_delete_injury_sheet_%s' % self.injury.id)

    def test_coach_has_no_foot(self):
        self._login_coach()
        _text, tree = self._get(self._card_url())
        card = tree.xpath('//details[@id="injury-%s"]' % self.injury.id)[0]
        self.assertFalse(card.xpath('.//div[contains(@class, "o_sc_injury_card_actions")]'))

    def test_done_buttons_marked(self):
        self._login_tp()
        _text, tree = self._get(self._card_url())
        for done in tree.xpath('//*[@data-sc-edit-card]//button[@data-sc-edit-done][contains(@class, "o_sc_btn_primary")]'):
            self.assertTrue('o_sc_edit_done' in done.get('class')
                            or 'o_sc_edit_done_actions' in done.getparent().get('class', ''), done.get('class'))


@tagged('post_install', '-at_install')
class TestDoneButtonsPrefI18n1676(Done1676Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.tp.write({'lang': 'fr_CA'})

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        return self._get(url)

    def test_french(self):
        self._login_tp()
        text, tree = self._fr('/my/app/settings')
        section = tree.xpath('//section[@data-sc-section="settings.done_buttons"]')[0]
        self.assertIn('Afficher les boutons Terminé', section.text_content())
        self.assertIn('terminer la modification', section.text_content())
        text, tree = self._fr(self._card_url())
        foot = tree.xpath('//div[contains(@class, "o_sc_injury_card_actions")]//button')[0]
        self.assertEqual(' '.join(foot.text_content().split()), 'Supprimer la blessure')

    def test_check_label_in_french(self):
        # The ✓'s label comes from the layout (a card may open on load,
        # before the JS translations are loaded).
        self._login_tp()
        _text, tree = self._fr('/my/app/settings')
        self.assertEqual(self._app(tree).get('data-sc-edit-done-label'), 'Terminer la modification')


class _DoneTours1676:

    def _player_info(self):
        return '/my/player?player_id=%s&tab=info' % self.player.id

    def test_default_check_closes(self):
        self.start_tour(self._player_info(), 'sc_1676_info_check', login='pc.tp@example.com')
        self.start_tour(self._card_url(), 'sc_1676_injury_check', login='pc.tp@example.com')

    def test_done_buttons_on(self):
        self.tp.write({'sc_show_done_buttons': True})
        self.start_tour(self._player_info(), 'sc_1676_info_done_on', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestDoneButtonsPhone1676(_DoneTours1676, Done1676Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestDoneButtonsLaptop1676(_DoneTours1676, Done1676Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
