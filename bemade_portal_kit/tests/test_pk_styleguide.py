# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5357 (P3b2): the kit's style guide page, ``/pk/styleguide``.

* UC-S1 An internal user (``base.group_user``) gets the page: one shell
  root ``.o_pk_app``, LIGHT by default (``data-pk-theme="light"``), dark
  with ``?theme=dark``; any other value falls back to light.
* UC-S2 A portal user gets a 404, a visitor is sent to the login page.
* UC-S3 The page uses kit names only: no consumer class (``o_sc_``) and no
  consumer attribute (``data-sc-``).
* UC-S4 (task 5369) Its icons are the kit's ``pk_icon``: the style guide has
  no icon template of its own any more.
* UC-S5 (task 5345) The page is drawn on the kit's app layout
  (``pk_app_layout``) with the neutral brand: the rail, the app bar with its
  user menu, ``main#pk_content``; no app-bar markup of its own; it shows the
  components the kit adopted in P3c2 (list header, card icons, history,
  switch, link row, entity row, static field with the overdue flag).
Synthetic users only.
"""
from odoo.tests import HttpCase, new_test_user, tagged

from .test_pk_icon import GOLDEN

URL = '/pk/styleguide'


@tagged('post_install', '-at_install')
class TestPkStyleguide(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal = new_test_user(cls.env, login='pk_sg_internal', groups='base.group_user')
        cls.portal = new_test_user(cls.env, login='pk_sg_portal', groups='base.group_portal')

    def test_internal_user_light_by_default(self):
        self.authenticate('pk_sg_internal', 'pk_sg_internal')
        res = self.url_open(URL)
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn('class="o_pk_app', html)
        self.assertIn('data-pk-theme="light"', html)
        self.assertIn('o_pk_app_body_light', html)
        self.assertNotIn('o_sc_', html)
        self.assertNotIn('data-sc-', html)

    def test_dark_theme_param(self):
        self.authenticate('pk_sg_internal', 'pk_sg_internal')
        html = self.url_open(URL + '?theme=dark').text
        self.assertIn('data-pk-theme="dark"', html)
        self.assertIn('o_pk_app_body_dark', html)
        html = self.url_open(URL + '?theme=purple').text
        self.assertIn('data-pk-theme="light"', html)

    def test_icons_are_pk_icon(self):
        self.assertFalse(self.env.ref('bemade_portal_kit.pk_styleguide_icon', raise_if_not_found=False))
        self.authenticate('pk_sg_internal', 'pk_sg_internal')
        html = self.url_open(URL).text
        for name in ('chevron', 'plus', 'close', 'edit', 'trash', 'moon'):
            self.assertIn(GOLDEN[name], html, name)

    def test_portal_user_not_found(self):
        self.authenticate('pk_sg_portal', 'pk_sg_portal')
        res = self.url_open(URL)
        self.assertEqual(res.status_code, 404)

    def test_visitor_redirected_to_login(self):
        res = self.url_open(URL, allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertIn('/web/login', res.headers.get('Location', ''))

    def test_on_the_kit_layout(self):
        self.authenticate('pk_sg_internal', 'pk_sg_internal')
        res = self.url_open(URL)
        self.assertEqual(res.status_code, 200)
        html = res.text
        for marker in ('data-pk-app-shell="1"', 'id="pk_content"', 'class="o_pk_rail"', 'o_pk_rail_brand',
                       'data-pk-user-menu-toggle', 'id="pk_user_menu_bar"', 'data-pk-guard-texts',
                       'o_pk_logo_mark', 'data-pk-nav-key="pk_sg_components"'):
            self.assertIn(marker, html, marker)
        self.assertEqual(html.count('<header class="o_pk_appbar"'), 1)
        self.assertIn('<meta name="theme-color" content="#ffffff"', html)
        view = self.env.ref('bemade_portal_kit.pk_styleguide')
        self.assertIn('bemade_portal_kit.pk_app_layout', view.arch_db)
        self.assertNotIn('web.frontend_layout', view.arch_db)
        self.assertNotIn('o_pk_appbar', view.arch_db)
        for component in ('data-pk-card-icons', 'o_pk_list_header', 'o_pk_history_entry', 'o_pk_switch_reason',
                          'data-pk-row-links', 'o_pk_entity_row', 'data-pk-overdue', 'o_pk_banner_warn'):
            self.assertIn(component, html, component)
