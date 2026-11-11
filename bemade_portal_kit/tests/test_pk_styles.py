# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5357 (P3b2): the shell's generic styles live in the kit.

* UC-T1 The kit bundles its four SCSS files in ``web.assets_frontend``, in
  order (variables, tokens, components, pages), and nowhere else at run time
  except the consumers' own bundles that need the variables / slot mixins.
* UC-T2 The compiled ``web.assets_frontend`` CSS compiles without error and
  holds the kit's NEUTRAL defaults: light on ``.o_pk_app`` (accent
  ``#2563eb``, system fonts, normal case) and dark under
  ``[data-pk-theme="dark"]`` (accent ``#60a5fa``).
* UC-T3 The kit's SCSS names no consumer: no ``o_sc_`` class, no
  ``data-sc-`` attribute, no ``--sc-`` token, no brand font (Teko,
  DM Sans), no web-font import.
"""
import glob
import os
import re

from odoo.modules.module import get_manifest, get_module_path
from odoo.tests import TransactionCase, tagged

KIT = 'bemade_portal_kit'
SCSS = ('pk_variables', 'pk_tokens', 'pk_components', 'pk_pages')
FORBIDDEN = ('o_sc_', 'data-sc-', '--sc-', '$sc-', 'Teko', 'DM Sans', '@import', 'fonts.googleapis')


def _block(css, selector_regex):
    """The declarations of the first rule whose selector matches."""
    match = re.search(selector_regex + r'\s*\{([^}]*)\}', css)
    return match.group(1) if match else ''


def _slots(block):
    return {k.strip(): v.strip() for k, v in re.findall(r'(--pk-[\w-]+)\s*:\s*([^;]+)', block)}


@tagged('post_install', '-at_install')
class TestPkStyles(TransactionCase):

    def test_scss_files_bundled_in_order(self):
        frontend = get_manifest(KIT)['assets']['web.assets_frontend']
        listed = [p for p in frontend if isinstance(p, str) and p.endswith('.scss')]
        self.assertEqual(listed, [f'{KIT}/static/src/scss/{name}.scss' for name in SCSS])
        root = os.path.join(get_module_path(KIT), 'static', 'src', 'scss')
        found = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(root, '*.scss')))
        self.assertEqual(found, sorted(SCSS))

    def test_kit_scss_names_no_consumer(self):
        root = os.path.join(get_module_path(KIT), 'static', 'src', 'scss')
        hits = []
        for path in sorted(glob.glob(os.path.join(root, '*.scss'))):
            with open(path, encoding='utf-8') as f:
                for lineno, line in enumerate(f, 1):
                    for word in FORBIDDEN:
                        if word in line:
                            hits.append(f'{os.path.basename(path)}:{lineno}: {word}')
        self.assertEqual(hits, [])

    def test_compiled_neutral_defaults(self):
        bundle = self.env['ir.qweb']._get_asset_bundle('web.assets_frontend', js=False)
        css = bundle.css().raw.decode()
        self.assertFalse(bundle.css_errors, bundle.css_errors)
        light = _slots(_block(css, r'\.o_pk_app,\s*body\.o_pk_app_body'))
        self.assertEqual(light.get('--pk-accent'), '#2563eb')
        self.assertEqual(light.get('--pk-bg'), '#f8fafc')
        self.assertEqual(light.get('--pk-color-scheme'), 'light')
        self.assertEqual(light.get('--pk-title-transform'), 'none')
        self.assertTrue(light.get('--pk-font-text', '').startswith('system-ui'))
        dark = _slots(_block(css, r'\.o_pk_app\[data-pk-theme="?dark"?\][^{]*'))
        self.assertEqual(dark.get('--pk-accent'), '#60a5fa')
        self.assertEqual(dark.get('--pk-bg'), '#0f172a')
        self.assertEqual(dark.get('--pk-color-scheme'), 'dark')
