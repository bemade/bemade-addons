"""Task 5345 (kit P3c2) — ``sc_app_layout`` is a thin wrapper of the kit's
app layout (``bemade_portal_kit.pk_app_layout``). Synthetic fixtures only.

Acceptance criteria covered here:

* UC-W1 The wrapper keeps its xmlid and t-calls the kit's layout: one shell
  root, ``main#pk_content``, the kit's user menu (``pk_user_menu_bar``).
* UC-W2 It fills the kit's slots with the clinic's pieces: the Fit Crew
  brand (name « Le Fit Crew », ``/my/home``, the chrome logo
  ``sc_logo_mark`` on the rail and the logo, the Fit Crew theme colours),
  the PWA head (manifest, apple touch icon, app title), the app-bar
  activity clock, help and search icons (in that order, before the user
  menu), the help-home item of the user menu, the search sheet, the
  injury-resolve and proposal dialogs; the guard params name ``ts_error``;
  the « Done » hiding and the home of ``pk_confirm.js`` (``/my/players``,
  ``player_id``).
* UC-W3 No kit default text shows: the kit's neutral mark is not used, the
  home picto reads « Dashboard ».
* UC-W4 The settings item of the user menu is the clinic's
  (``/my/app/settings``), current on that page.
"""

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_user_menu_1606 import UserMenuCommon


@tagged('post_install', '-at_install')
class TestPkLayoutWrapper5345(UserMenuCommon):

    def test_wrapper_calls_the_kit_layout(self):
        view = self.env.ref('bemade_sports_clinic.sc_app_layout')
        self.assertIn('bemade_portal_kit.pk_app_layout', view.arch_db)
        self.assertNotIn('pk_frontend_layout', view.arch_db)
        self.assertNotIn('o_pk_rail', view.arch_db)
        # The clinic's old popup is gone (adopted by the kit).
        self.assertFalse(self.env['ir.model.data'].search_count(
            [('module', '=', 'bemade_sports_clinic'), ('name', '=', 'sc_user_menu_popup')]))

    def test_slots_filled_for_a_therapist(self):
        self._switch(True)
        self.tp.pk_show_done_buttons = False  # the default (the common fixture turns it on)
        self._login_tp()
        text, tree = self._get('/my/players')
        app = self._shell(tree)
        self.assertEqual(len(tree.xpath('//*[@data-pk-app-shell]')), 1)
        self.assertEqual(len(tree.xpath('//main[@id="pk_content"]')), 1)
        # Brand.
        brand = app.xpath('.//a[contains(@class, "o_pk_rail_brand")]')[0]
        self.assertEqual(brand.get('href'), '/my/home')
        self.assertEqual(brand.xpath('.//span[@class="o_pk_rail_brand_name"]/text()'), ['Le Fit Crew'])
        self.assertEqual(len(app.xpath('.//img[@class="o_pk_logo_mark"][contains(@src, "sc_logo_chrome")]')), 2)
        self.assertFalse(app.xpath('.//svg[contains(@class, "o_pk_logo_mark")]'))
        self.assertEqual(app.get('data-pk-theme-color-dark'), '#120e12')
        self.assertEqual(app.get('data-pk-theme-color-light'), '#243925')
        self.assertEqual(tree.xpath('//meta[@name="theme-color"]/@content'), ['#120e12'])
        self.assertEqual((app.get('data-pk-home'), app.get('data-pk-home-same-params')), ('/my/players', 'player_id'))
        self.assertEqual(app.get('data-pk-hide-done'), '1')
        # PWA head.
        self.assertEqual(tree.xpath('//head/link[@rel="manifest"]/@href'), ['/my/app.webmanifest'])
        self.assertTrue(tree.xpath('//head/link[@rel="apple-touch-icon"]'))
        self.assertEqual(tree.xpath('//head/meta[@name="apple-mobile-web-app-title"]/@content'), ['Fit Crew'])
        # App-bar actions: clock, help (when the page has an article), search; before the user menu.
        header = app.xpath('.//header[contains(@class, "o_pk_appbar")]')[0]
        kinds = []
        for el in header:
            if el.get('data-sc-activity-clock-bar'):
                kinds.append('clock')
            elif el.get('data-pk-help'):
                kinds.append('help')
            elif el.get('data-pk-search-open'):
                kinds.append('search')
            elif 'o_pk_user_menu_bar' in (el.get('class') or ''):
                kinds.append('menu')
        self.assertEqual([k for k in kinds if k != 'help'], ['clock', 'search', 'menu'])
        self.assertEqual(kinds[-1], 'menu')
        # Sheets and dialogs after the content.
        main_index = None
        for index, el in enumerate(app.xpath('.//div[@class="o_pk_main"]')[0]):
            if el.tag == 'main':
                main_index = index
            for sheet_id in ('pk_search_sheet', 'sc_injury_resolve_sheet', 'sc_proposal_sheet'):
                if el.get('id') == sheet_id:
                    self.assertGreater(index, main_index, sheet_id)
        for sheet_id in ('pk_search_sheet', 'sc_injury_resolve_sheet', 'sc_proposal_sheet'):
            self.assertEqual(len(tree.xpath('//dialog[@id="%s"]' % sheet_id)), 1, sheet_id)
        self.assertEqual(app.xpath('.//span[@data-pk-guard-texts]/@data-pk-guard-error-params'), ['error ts_error'])

    def test_user_menu_items(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/app/settings')
        popup = tree.xpath('//div[@id="pk_user_menu_bar"]')[0]
        settings = popup.xpath('.//a[@href="/my/app/settings"]')[0]
        self.assertEqual(settings.get('aria-current'), 'page')
        hrefs = popup.xpath('.//a[@role="menuitem"]/@href')
        self.assertEqual(hrefs[0], '/my/app/settings')
        self.assertTrue(hrefs[-1].startswith('/web/session/logout'))
        _text, tree = self._get('/my/home')
        popup = tree.xpath('//div[@id="pk_user_menu_bar"]')[0]
        self.assertIsNone(popup.xpath('.//a[@href="/my/app/settings"]')[0].get('aria-current'))

    def test_sub_page_home_picto(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/app/settings')
        picto = tree.xpath('//a[contains(@class, "o_pk_home_picto")]')[0]
        self.assertEqual((picto.get('href'), picto.get('aria-label')), ('/my/home', 'Dashboard'))
        self.assertTrue(picto.xpath('.//img[contains(@src, "sc_logo_chrome")]'))
        self.assertEqual(self._shell(tree).get('data-pk-top'), '0')
