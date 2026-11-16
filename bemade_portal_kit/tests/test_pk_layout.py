# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5345 (kit P3c2): the kit's app layout, its user menu and brand.

* UC-L1 ``bemade_portal_kit.pk_app_layout`` renders with the kit alone and
  no value: one shell root ``.o_pk_app`` (light, ``data-pk-top="1"``), the
  neutral brand (``portal.kit.pk_brand()``: the company name, ``/my``, the
  kit's mark and theme colours), the content area ``main#pk_content``
  holding the body, the form guard's texts, the toast host and the user
  menu; no theme toggle, no « Done » hiding, no consumer name.
* UC-L2 The values drive it: rail and tabs (``data-pk-nav-key``, the active
  one ``aria-current``), a sub-page (back chevron, home picto, crumbs, the
  context line, ``data-pk-top="0"``), the title and its fragments
  (``pk_page_key``), dark theme and its colour, the theme toggle (only with
  ``pk_theme_choice`` AND ``pk_pref_url``; it posts ``pk_theme_field``),
  ``data-pk-hide-done`` when ``pk_show_done`` is False, the user menu (head,
  settings item and its active state), ``data-pk-home``, the guard params.
* UC-L3 Each slot (``pk_head_extra``, ``pk_brand_mark``,
  ``pk_appbar_actions``, ``pk_user_menu_extra``, ``pk_layout_sheets``) is
  empty by default and rendered where it belongs when filled; a page's
  ``pk_brand`` is merged over the defaults.
* UC-L4 ``portal.kit.pk_brand()``: neutral defaults, extended through the
  hook ``_pk_brand()``; overrides merged, the theme colours too.
* UC-L5 The user menu popup is the kit's (adopted from the first consumer:
  ``pk_user_menu_popup``).
* UC-L6 (task 5392) One portal app per instance: the brand an app registers
  (``_pk_apps()[app]['brand']``) is the whole shell's, for every viewer,
  a user without an app role included; a page's ``pk_brand`` still wins.
  UC-L1..L4 check the kit's own look: they set aside whatever app a
  consumer registered (``pk_no_apps``) and force an English site.
Synthetic values only.
"""
import re

from lxml import html as lxml_html

from odoo.tests import TransactionCase, tagged

from odoo.addons.http_routing.tests.common import MockRequest

from .common import pk_frontend_langs, pk_hooks, pk_no_apps

KIT = 'bemade_portal_kit'
CONSUMER_RE = re.compile(r'data-sc-|o_sc_|\bsc_|bemade_sports_clinic')


@tagged('post_install', '-at_install')
class TestPkLayout(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Task 5392: the English texts and unprefixed URLs asserted below.
        pk_frontend_langs(cls.env)
        cls.env = cls.env(context=dict(cls.env.context, lang='en_US'))

    def setUp(self):
        super().setUp()
        # Task 5392: the kit's own look, whatever app a consumer registered.
        no_apps = pk_no_apps(self.env)
        no_apps.__enter__()
        self.addCleanup(no_apps.__exit__, None, None, None)

    def _render(self, values=None, body='<p class="pk_t_body">Body</p>', slots=None):
        """Render a synthetic page on the kit layout: ``slots`` are t-set
        bodies (markup) in the call, ``values`` plain values."""
        slots = ''.join('<t t-set="%s">%s</t>' % item for item in (slots or {}).items())
        arch = ('<t t-name="pk_t_page"><t t-call="bemade_portal_kit.pk_app_layout">%s%s</t></t>'
                % (slots, body))
        view = self.env['ir.ui.view'].create({'name': 'pk_t_page', 'type': 'qweb', 'arch': arch})
        # The kit does not depend on website; when a database has it, the
        # frontend render needs the request's website.
        website = self.env['website'].get_current_website() if 'website' in self.env else None
        with MockRequest(self.env, path='/pk/t', website=website, url_root='http://localhost/') as request:
            request.csrf_token = lambda *a, **k: 'pk-t-token'
            request.is_frontend = True
            # Through the request's env (its language) and the view's render
            # (which gives website its main object), as a controller would.
            out = request.env['ir.ui.view']._render_template(view.id, dict(values or {}))
        return lxml_html.document_fromstring(str(out))

    def _app(self, tree):
        apps = tree.xpath('//div[contains(concat(" ", @class, " "), " o_pk_app ")]')
        self.assertEqual(len(apps), 1)
        return apps[0]

    # ------------------------------------------------------------- UC-L1
    def test_bare_layout(self):
        tree = self._render()
        app = self._app(tree)
        self.assertEqual(app.get('data-pk-theme'), 'light')
        self.assertEqual(app.get('data-pk-top'), '1')
        self.assertIsNone(app.get('data-pk-hide-done'))
        self.assertEqual(app.get('data-pk-edit-done-label'), 'Finish editing')
        self.assertIn('o_pk_app_body_light', tree.xpath('//body/@class')[0])
        main = tree.xpath('//main[@id="pk_content"]')
        self.assertEqual(len(main), 1)
        self.assertTrue(main[0].xpath('.//p[@class="pk_t_body"]'))
        # The neutral brand: the company name, /my, the kit's mark.
        brand = app.xpath('.//a[contains(@class, "o_pk_rail_brand")]')[0]
        self.assertEqual(brand.get('href'), '/my')
        self.assertEqual(brand.xpath('.//span[@class="o_pk_rail_brand_name"]/text()'), [self.env.company.name])
        self.assertTrue(brand.xpath('.//svg[contains(@class, "o_pk_logo_mark")]'))
        logo = app.xpath('.//header//a[contains(@class, "o_pk_logo")]')[0]
        self.assertEqual(logo.get('aria-label'), self.env.company.name)
        self.assertEqual(tree.xpath('//meta[@name="theme-color"]/@content'), ['#ffffff'])
        self.assertFalse(app.xpath('.//form[@data-pk-pref]'))
        self.assertFalse(app.xpath('.//*[contains(@class, "o_pk_back")]'))
        self.assertFalse(app.xpath('.//nav[contains(@class, "o_pk_crumbs")]'))
        # The kit's pieces of every page.
        texts = app.xpath('.//span[@data-pk-guard-texts]')
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0].get('data-pk-guard-error-params'), 'error')
        self.assertEqual(texts[0].get('data-missing'), 'Complete:')
        self.assertTrue(app.xpath('.//div[contains(@class, "o_pk_toast")]'))
        toggle = app.xpath('.//button[@data-pk-user-menu-toggle][@aria-controls="pk_user_menu_bar"]')
        self.assertEqual(len(toggle), 1)
        self.assertTrue(app.xpath('.//div[@id="pk_user_menu_bar"][@data-pk-user-menu-popup]'))
        self.assertTrue(app.xpath('.//div[@data-pk-user-menu="bar"]'))
        # No settings item without a URL; the logout always.
        items = app.xpath('.//div[@id="pk_user_menu_bar"]//a[@role="menuitem"]/@href')
        self.assertEqual(items, ['/web/session/logout?redirect=/'])
        self.assertNotRegex(lxml_html.tostring(app, encoding='unicode'), CONSUMER_RE)

    # ------------------------------------------------------------- UC-L2
    def _nav(self):
        return [
            {'key': 'home', 'url': '/pk/t/home', 'icon': 'home', 'label': 'Home'},
            {'key': 'items', 'url': '/pk/t/items', 'icon': 'list', 'label': 'Items'},
        ]

    def test_rail_tabs_active(self):
        app = self._app(self._render({'pk_rail': self._nav(), 'pk_tabs': self._nav()[:1], 'pk_active_nav': 'items'}))
        rail = app.xpath('.//nav[contains(@class, "o_pk_rail_nav")]//a')
        self.assertEqual([a.get('data-pk-nav-key') for a in rail], ['home', 'items'])
        self.assertEqual([a.get('aria-current') for a in rail], [None, 'page'])
        tabs = app.xpath('.//nav[contains(@class, "o_pk_tabs")]//a')
        self.assertEqual([a.get('data-pk-nav-key') for a in tabs], ['home'])
        self.assertEqual(tabs[0].get('href'), '/pk/t/home')

    def test_sub_page(self):
        tree = self._render({
            'pk_title': 'Item 7', 'pk_parent_url': '/pk/t/items', 'pk_context': 'Group A',
            'pk_crumbs': [('Items', '/pk/t/items')], 'pk_page_key': 'res.partner:7',
            'pk_content_class': 'o_pk_content_wide',
        })
        app = self._app(tree)
        self.assertEqual(app.get('data-pk-top'), '0')
        self.assertEqual(tree.xpath('//title/text()')[0].strip(), 'Item 7')
        back = app.xpath('.//a[@data-pk-back="1"]')[0]
        self.assertEqual((back.get('href'), back.get('aria-label')), ('/pk/t/items', 'Back'))
        picto = app.xpath('.//a[contains(@class, "o_pk_home_picto")]')[0]
        self.assertEqual((picto.get('href'), picto.get('aria-label')), ('/my', 'Home'))
        self.assertFalse(app.xpath('.//header//a[contains(@class, "o_pk_logo")]'))
        title = app.xpath('.//h1[contains(@class, "o_pk_appbar_title")]')[0]
        self.assertEqual(title.get('data-pk-fragment'), 'res.partner:7:appbar')
        self.assertEqual(title.xpath('.//small[contains(@class, "o_pk_appbar_context")]/text()'), ['Group A'])
        crumbs = app.xpath('.//nav[contains(@class, "o_pk_crumbs")]//li')
        self.assertEqual(crumbs[0].xpath('./a/@href'), ['/pk/t/items'])
        self.assertEqual(crumbs[-1].get('data-pk-fragment'), 'res.partner:7:crumb')
        self.assertEqual(crumbs[-1].text, 'Item 7')
        self.assertIn('o_pk_content_wide', app.xpath('.//main[@id="pk_content"]/@class')[0])

    def test_theme_and_toggle(self):
        values = {'pk_theme': 'dark', 'pk_theme_choice': True, 'pk_current_url': '/pk/t?x=1'}
        tree = self._render(values)
        app = self._app(tree)
        self.assertEqual(app.get('data-pk-theme'), 'dark')
        self.assertIn('o_pk_app_body_dark', tree.xpath('//body/@class')[0])
        self.assertEqual(tree.xpath('//meta[@name="theme-color"]/@content'), ['#020617'])
        self.assertEqual((app.get('data-pk-theme-color-light'), app.get('data-pk-theme-color-dark')),
                         ('#ffffff', '#020617'))
        # No pref URL: no toggle, even with the choice on.
        self.assertFalse(app.xpath('.//form[@data-pk-pref]'))
        app = self._app(self._render(dict(values, pk_pref_url='/pk/t/pref')))
        form = app.xpath('.//form[@data-pk-pref="1"]')[0]
        self.assertEqual(form.get('action'), '/pk/t/pref')
        self.assertEqual(form.xpath('.//input[@name="redirect"]/@value'), ['/pk/t?x=1'])
        button = form.xpath('.//button[@data-pk-theme-toggle]')[0]
        self.assertEqual((button.get('name'), button.get('value')), ('pk_theme', 'light'))
        app = self._app(self._render(dict(values, pk_pref_url='/pk/t/pref', pk_theme_field='pk_t_theme')))
        self.assertEqual(app.xpath('.//button[@data-pk-theme-toggle]/@name'), ['pk_t_theme'])
        app = self._app(self._render(dict(values, pk_pref_url='/pk/t/pref', pk_theme_choice=False)))
        self.assertFalse(app.xpath('.//form[@data-pk-pref]'))
        # An unknown theme falls back to light.
        self.assertEqual(self._app(self._render({'pk_theme': 'purple'})).get('data-pk-theme'), 'light')

    def test_done_home_guard_user(self):
        app = self._app(self._render({
            'pk_show_done': False, 'pk_edit_done_label': 'Close the card',
            'pk_home_url': '/pk/t/items', 'pk_home_same_params': 'item_id', 'pk_guard_params': 'error other_error',
            'pk_db': 'pk_t_db', 'pk_uid': 7,
            'pk_user_initials': 'TU', 'pk_user_name': 'Test User', 'pk_user_role': 'Tester',
            'pk_settings_url': '/pk/t/settings', 'pk_settings_active': True,
        }))
        self.assertEqual(app.get('data-pk-hide-done'), '1')
        self.assertEqual(app.get('data-pk-edit-done-label'), 'Close the card')
        self.assertEqual((app.get('data-pk-home'), app.get('data-pk-home-same-params')), ('/pk/t/items', 'item_id'))
        self.assertEqual((app.get('data-pk-db'), app.get('data-pk-uid')), ('pk_t_db', '7'))
        self.assertEqual(app.xpath('.//span[@data-pk-guard-texts]/@data-pk-guard-error-params'), ['error other_error'])
        self.assertEqual(app.xpath('.//button[@data-pk-user-menu-toggle]//span[@class="o_pk_avatar"]/text()'), ['TU'])
        popup = app.xpath('.//div[@id="pk_user_menu_bar"]')[0]
        self.assertEqual(' '.join(''.join(popup.xpath('.//*[@data-pk-user-menu-head]//text()')).split()),
                         'TU Test User Tester')
        settings = popup.xpath('.//a[@href="/pk/t/settings"]')[0]
        self.assertEqual(settings.get('aria-current'), 'page')
        self.assertEqual(settings.get('role'), 'menuitem')
        app = self._app(self._render({'pk_show_done': True}))
        self.assertIsNone(app.get('data-pk-hide-done'))

    # ------------------------------------------------------------- UC-L3
    def test_slots_filled(self):
        tree = self._render({'pk_settings_url': '/pk/t/settings'}, slots={
            'pk_head_extra': '<meta name="pk-t-head" content="1"/>',
            'pk_brand_mark': '<img class="o_pk_logo_mark pk_t_mark" src="/pk/t.png" alt=""/>',
            'pk_appbar_actions': '<a class="o_pk_icon_btn pk_t_action" href="/pk/t/act">A</a>',
            'pk_user_menu_extra': '<a role="menuitem" class="o_pk_user_menu_item pk_t_extra" href="/pk/t/x">X</a>',
            'pk_layout_sheets': '<dialog id="pk_t_sheet" class="o_pk_sheet"/>',
        })
        app = self._app(tree)
        self.assertTrue(tree.xpath('//head/meta[@name="pk-t-head"]'))
        self.assertEqual(len(app.xpath('.//img[contains(@class, "pk_t_mark")]')), 2)  # rail + logo
        self.assertFalse(app.xpath('.//svg[contains(@class, "o_pk_logo_mark")]'))
        header = app.xpath('.//header[contains(@class, "o_pk_appbar")]')[0]
        kids = [el.get('class') or '' for el in header]
        action = [i for i, c in enumerate(kids) if 'pk_t_action' in c]
        menu = [i for i, c in enumerate(kids) if 'o_pk_user_menu_bar' in c]
        self.assertEqual(len(action), 1)
        self.assertLess(action[0], menu[0], 'the actions come before the user menu')
        items = app.xpath('.//div[@id="pk_user_menu_bar"]//a[@role="menuitem"]/@href')
        self.assertEqual(items, ['/pk/t/settings', '/pk/t/x', '/web/session/logout?redirect=/'])
        sheet = app.xpath('.//dialog[@id="pk_t_sheet"]')[0]
        self.assertEqual(sheet.getparent().get('class'), 'o_pk_main')
        main = app.xpath('.//main[@id="pk_content"]')[0]
        self.assertGreater(sheet.getparent().index(sheet), main.getparent().index(main))
        self.assertFalse(main.xpath('.//dialog'))

    def test_slots_see_the_page(self):
        """The sheets slot renders after the body: what the body leaves for
        it (a value its rendering set) is there."""
        tree = self._render(
            {'pk_t_seen': []},
            body='<t t-set="pk_t_dummy" t-value="pk_t_seen.append(1)"/><p>Body</p>',
            slots={'pk_layout_sheets': '<span class="pk_t_count" t-out="len(pk_t_seen)"/>'},
        )
        self.assertEqual(tree.xpath('//span[@class="pk_t_count"]/text()'), ['1'])

    def test_page_brand_merged(self):
        tree = self._render({'pk_brand': {'name': 'Sample App', 'home_url': '/pk/t/home',
                                          'theme_colors': {'light': '#123456'}}})
        app = self._app(tree)
        brand = app.xpath('.//a[contains(@class, "o_pk_rail_brand")]')[0]
        self.assertEqual(brand.get('href'), '/pk/t/home')
        self.assertEqual(brand.xpath('.//span[@class="o_pk_rail_brand_name"]/text()'), ['Sample App'])
        self.assertEqual(tree.xpath('//meta[@name="theme-color"]/@content'), ['#123456'])
        self.assertEqual(app.get('data-pk-theme-color-dark'), '#020617')

    # ------------------------------------------------------------- UC-L4
    def test_brand_defaults(self):
        kit = self.env['portal.kit']
        brand = kit.pk_brand()
        self.assertEqual(brand['name'], self.env.company.name)
        self.assertEqual(brand['home_url'], '/my')
        self.assertEqual(brand['home_label'], 'Home')
        self.assertEqual(brand['theme_colors'], {'light': '#ffffff', 'dark': '#020617'})
        merged = kit.pk_brand({'name': 'Sample App', 'theme_colors': {'dark': '#000000'}})
        self.assertEqual(merged['name'], 'Sample App')
        self.assertEqual(merged['home_url'], '/my')
        self.assertEqual(merged['theme_colors'], {'light': '#ffffff', 'dark': '#000000'})
        # A fresh dict every call: a caller's change never leaks.
        merged['name'] = 'changed'
        self.assertEqual(kit.pk_brand()['name'], self.env.company.name)

    # ------------------------------------------------------------- UC-L5
    def test_user_menu_popup_is_the_kits(self):
        view = self.env.ref('%s.pk_user_menu_popup' % KIT)
        self.assertEqual(view.key, '%s.pk_user_menu_popup' % KIT)
        self.assertTrue(self.env.ref('%s.pk_app_layout' % KIT))

    # ------------------------------------------------------------- UC-L6
    def test_app_brand_is_the_whole_shells(self):
        """The instance's app brand: on the layout for a viewer without an
        app role (here the test's user), its home in the logo and the home
        picto, its colours; a page's own ``pk_brand`` is merged over it."""
        apps = {'pk_t_app': {'brand': {'name': 'Sample App', 'home_url': '/pk/t/home',
                                       'theme_colors': {'light': '#0b2a4a', 'dark': '#0b2a4a'}}}}
        roles = {'pk_t_member': {'groups': ('base.group_portal',), 'app': 'pk_t_app'}}
        with pk_hooks(self.env, _pk_apps=lambda _orig: apps, _pk_roles=lambda _orig: roles):
            self.assertFalse(self.env['portal.kit']._pk_app(), 'the viewer holds no app role')
            self.assertEqual(self.env['portal.kit']._pk_current_app(), 'pk_t_app')
            tree = self._render()
            app = self._app(tree)
            brand = app.xpath('.//a[contains(@class, "o_pk_rail_brand")]')[0]
            self.assertEqual(brand.get('href'), '/pk/t/home')
            self.assertEqual(brand.xpath('.//span[@class="o_pk_rail_brand_name"]/text()'), ['Sample App'])
            self.assertEqual(app.xpath('.//header//a[contains(@class, "o_pk_logo")]/@href'), ['/pk/t/home'])
            self.assertEqual(tree.xpath('//meta[@name="theme-color"]/@content'), ['#0b2a4a'])
            self.assertEqual((app.get('data-pk-theme-color-light'), app.get('data-pk-theme-color-dark')),
                             ('#0b2a4a', '#0b2a4a'))
            picto = self._app(self._render({'pk_parent_url': '/pk/t/items'})).xpath(
                './/a[contains(@class, "o_pk_home_picto")]/@href')
            self.assertEqual(picto, ['/pk/t/home'])
            tree = self._render({'pk_brand': {'home_url': '/pk/t/page', 'theme_colors': {'light': '#123456'}}})
            self.assertEqual(self._app(tree).xpath('.//a[contains(@class, "o_pk_rail_brand")]/@href'), ['/pk/t/page'])
            self.assertEqual(tree.xpath('//meta[@name="theme-color"]/@content'), ['#123456'])
        # No app registered: the neutral look again.
        tree = self._render()
        self.assertEqual(self._app(tree).xpath('.//a[contains(@class, "o_pk_rail_brand")]/@href'), ['/my'])
        self.assertEqual(tree.xpath('//meta[@name="theme-color"]/@content'), ['#ffffff'])
