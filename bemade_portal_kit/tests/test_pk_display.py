# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5381 (kit P4c2): the edit cards, sheets, tabs and clamps.

* UC-D1 ``tools/display.py`` (pure functions): ``pk_display(record, field)``
  is a value as a reader sees it (the save route answers the same string),
  ``pk_display_key(record, field)`` the ``model:id:field`` key a save
  refreshes, ``pk_contact_href(kind, value)`` a tap-to-call / tap-to-email
  href (or None).
* UC-D2 The four templates the kit adopted in this phase
  (``pk_edit_card_head``, ``pk_display_row``, ``pk_sheet``,
  ``pk_page_tabs``) render with the kit alone: the only helpers they need
  are the three above, passed by the caller.
* UC-D3 The kit's styles: the generic line clamp ``[data-pk-clamp="N"]``
  (N = 1 to 6, ``:not([data-pk-clamp-open])``), the contact link
  ``a.o_pk_contact_link[href]`` and the edit view's ``[hidden]``.
* UC-D4 The kit's scripts are bundled (frontend + unit tests).
Synthetic data only.
"""
import re
from unittest.mock import MagicMock

from lxml import html as lxml_html

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit.controllers.pk_app import PortalKitApp
from odoo.addons.bemade_portal_kit.tools import display as pk_display_tools
from odoo.addons.bemade_portal_kit.tools import pk_contact_href, pk_display, pk_display_key

KIT = 'bemade_portal_kit'
NEW_JS = ('edit_cards', 'sheets', 'tabs', 'clamp', 'shell')


@tagged('post_install', '-at_install')
class TestPkDisplay(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Pk Test Person', 'phone': '+1 (555) 010-0123', 'email': 'pk.test@example.com',
        })

    # ------------------------------------------------------------- UC-D1
    def test_display(self):
        self.assertEqual(pk_display(self.partner, 'name'), 'Pk Test Person')
        self.assertEqual(pk_display(self.partner, 'website'), '')
        self.assertEqual(pk_display(self.partner, 'no_such_field'), '')
        self.partner.country_id = self.env.ref('base.ca')
        self.assertEqual(pk_display(self.partner, 'country_id'), self.env.ref('base.ca').name)
        # The save route answers the same string.
        self.assertEqual(PortalKitApp._pk_save_display(self.partner, 'country_id'),
                         pk_display(self.partner, 'country_id'))

    def test_display_key(self):
        self.assertEqual(pk_display_key(self.partner, 'phone'), 'res.partner:%s:phone' % self.partner.id)

    def test_contact_href(self):
        self.assertEqual(pk_contact_href('tel', '+1 (555) 010-0123'), 'tel:+15550100123')
        self.assertEqual(pk_contact_href('tel', 'call me'), None)
        self.assertEqual(pk_contact_href('mailto', ' a@example.com '), 'mailto:a@example.com')
        self.assertEqual(pk_contact_href('tel', ''), None)
        self.assertEqual(pk_contact_href('tel', False), None)
        self.assertEqual(pk_contact_href('fax', '1'), None)

    def test_display_module_is_pure(self):
        for name, value in vars(pk_display_tools).items():
            if not name.startswith('__'):
                self.assertNotIsInstance(value, (dict, list, set), name)

    # ------------------------------------------------------------- UC-D2
    def _render(self, name, values):
        fake = MagicMock()
        fake.csrf_token.return_value = 'pk-t-token'
        values = dict(values, request=fake)
        out = self.env['ir.qweb'].with_context(minimal_qcontext=True)._render('%s.%s' % (KIT, name), values)
        return lxml_html.fragment_fromstring(str(out), create_parent='div')

    def _helpers(self):
        return {'pk_display': pk_display, 'pk_display_key': pk_display_key, 'pk_contact_href': pk_contact_href}

    def assertNoClinic(self, root):
        markup = lxml_html.tostring(root, encoding='unicode')
        self.assertNotRegex(markup, re.compile(r'data-sc-|o_sc_|sc_'))

    def test_edit_card_head(self):
        root = self._render('pk_edit_card_head', {'title': 'Identity', 'editable': True})
        self.assertEqual(root.xpath('.//h3[@class="o_pk_edit_card_title"]/text()'), ['Identity'])
        button = root.xpath('.//button[@data-pk-edit-toggle="1"]')
        self.assertEqual(len(button), 1)
        self.assertEqual(button[0].get('aria-expanded'), 'false')
        self.assertEqual(button[0].get('aria-label'), 'Edit')
        self.assertTrue(button[0].xpath('.//svg'))
        self.assertNoClinic(root)
        root = self._render('pk_edit_card_head', {'title': 'Identity', 'editable': False})
        self.assertFalse(root.xpath('.//button'))

    def test_display_row(self):
        values = dict(self._helpers(), label='Name', record=self.partner, field='name')
        root = self._render('pk_display_row', values)
        self.assertEqual(root.xpath('.//dt/text()'), ['Name'])
        span = root.xpath('.//dd/span')[0]
        self.assertEqual(span.get('data-pk-display'), 'res.partner:%s:name' % self.partner.id)
        self.assertEqual(span.text, 'Pk Test Person')
        self.assertNoClinic(root)

    def test_display_row_contact_link(self):
        values = dict(self._helpers(), label='Phone', record=self.partner, field='phone', href_kind='tel')
        link = self._render('pk_display_row', values).xpath('.//a')[0]
        self.assertEqual(link.get('class'), 'o_pk_contact_link')
        self.assertEqual(link.get('href'), 'tel:+15550100123')
        self.assertEqual(link.get('data-pk-display-href'), 'tel')
        self.assertEqual(link.get('data-pk-display'), 'res.partner:%s:phone' % self.partner.id)
        # Empty: « — », no href.
        values.update(field='mobile')
        link = self._render('pk_display_row', values).xpath('.//a')[0]
        self.assertIsNone(link.get('href'))
        self.assertEqual(link.text, '—')

    def test_sheet(self):
        root = self._render('pk_sheet', {'sheet_id': 'pk_t_sheet', 'title': 'History',
                                         'lazy_url': '/pk/t/history', 'lazy_fresh': True})
        dialog = root.xpath('.//dialog')[0]
        self.assertEqual(dialog.get('id'), 'pk_t_sheet')
        self.assertEqual(dialog.get('class'), 'o_pk_sheet')
        self.assertEqual(dialog.get('data-pk-lazy-url'), '/pk/t/history')
        self.assertEqual(dialog.get('data-pk-lazy-fresh'), '1')
        self.assertIsNone(dialog.get('data-pk-sheet-open-on-load'))
        self.assertEqual(root.xpath('.//button[@data-pk-sheet-close="1"]/@aria-label'), ['Close'])
        self.assertEqual(root.xpath('.//p[contains(@class, "o_pk_lazy_loading")]/text()'), ['Loading…'])
        self.assertNoClinic(root)
        root = self._render('pk_sheet', {'sheet_id': 'pk_t_s2', 'title': 'T', 'open_on_load': True})
        dialog = root.xpath('.//dialog')[0]
        self.assertEqual(dialog.get('data-pk-sheet-open-on-load'), '1')
        self.assertIsNone(dialog.get('data-pk-lazy-url'))

    def test_page_tabs(self):
        tabs = [
            ('overview', 'Overview', '/pk/t?tab=overview'),
            ('notes', 'Notes', '/pk/t?tab=notes', 'old-notes other', {'count': 3, 'tone': 'red', 'label': '3 new'}),
            ('docs', 'Documents', '/pk/t?tab=docs', None, None, 'Docs'),
        ]
        root = self._render('pk_page_tabs', {'tabs': tabs, 'active': 'notes'})
        nav = root.xpath('.//nav')[0]
        self.assertEqual(nav.get('data-pk-tabs'), '1')
        links = nav.xpath('./a')
        self.assertEqual([a.get('data-pk-tab') for a in links], ['overview', 'notes', 'docs'])
        self.assertEqual([a.get('aria-selected') for a in links], ['false', 'true', 'false'])
        self.assertEqual(links[1].get('data-pk-tab-aliases'), 'old-notes other')
        self.assertIsNone(links[0].get('data-pk-tab-aliases'))
        self.assertEqual(links[1].xpath('.//span[contains(@class, "o_pk_tab_badge_red")]/text()'), ['3'])
        self.assertEqual(links[2].get('title'), 'Documents')
        self.assertEqual(links[2].xpath('.//span[contains(@class, "o_pk_tab_label_short")]/text()'), ['Docs'])
        self.assertNoClinic(root)

    # ------------------------------------------------------------- UC-D3
    def test_styles(self):
        bundle = self.env['ir.qweb']._get_asset_bundle('web.assets_frontend', js=False)
        css = re.sub(r'\s+', ' ', bundle.css().raw.decode())
        self.assertFalse(bundle.css_errors, bundle.css_errors)
        for lines in range(1, 7):
            rule = re.search(r'\.o_pk_app \[data-pk-clamp="?%s"?\]:not\(\[data-pk-clamp-open\]\) ?\{([^}]*)\}'
                             % lines, css)
            self.assertTrue(rule, 'clamp %s' % lines)
            self.assertIn('-webkit-line-clamp: %s' % lines, rule.group(1))
        self.assertRegex(css, r'\.o_pk_app a\.o_pk_contact_link\[href\]')
        self.assertRegex(css, r'\.o_pk_app \.o_pk_edit_card \[data-pk-edit-view\]\[hidden\]')

    # ------------------------------------------------------------- UC-D4
    def test_scripts_bundled(self):
        assets = get_manifest(KIT)['assets']
        for name in NEW_JS:
            path = '%s/static/src/js/pk_%s.js' % (KIT, name)
            self.assertIn(path, assets['web.assets_frontend'])
            self.assertIn(path, assets['web.assets_unit_tests_setup'])
