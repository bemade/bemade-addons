# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5197 (P2): the kit's scripts are bundled once.

* every kit ``static/src/js/pk_*.js`` is listed by the kit itself, in
  exactly ONE runtime bundle (``web.assets_frontend``): a second listing,
  by the kit or by any other addon on the path (a consumer still listing
  its old copy), would run the module twice and bind its listeners twice.
  The hoot test bundles (``web.assets_unit_tests*``) are not runtime
  bundles: there the modules are only defined, and run per test file;
* task 5198 (P3a): the consumers' one-release aliases of the moved modules
  (« kit shims ») are gone: no bundled file is one any more, and the clinic's
  10 old paths no longer exist.
"""
import fnmatch
import glob
import os

from odoo.modules.module import get_manifest, get_module_path, get_modules
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import file_open

KIT = 'bemade_portal_kit'
KIT_JS = (
    'app_nav', 'confirm', 'contact_href', 'date_bounds', 'draft_store',
    'edit_anchor', 'fetch', 'focus', 'forms', 'list_header', 'live_count',
    'switch', 'user_menu',
)
SHIM_MARKER = 'bemade_portal_kit shim'
# The clinic's aliases removed by task 5198 (P3a).
CLINIC_SHIMS = (
    'fetch', 'draft_store', 'confirm', 'focus', 'date_bounds', 'contact_href',
    'user_menu', 'edit_anchor', 'list_header', 'app_nav',
)


def _asset_paths(entries):
    for entry in entries:
        if isinstance(entry, str):
            yield entry
        elif isinstance(entry, (list, tuple)) and entry:
            op = entry[0]
            if op in ('prepend', 'append') and len(entry) > 1:
                yield entry[1]
            elif op in ('before', 'after', 'replace') and len(entry) > 2:
                yield entry[2]


def _runtime_bundles(manifest):
    for bundle, entries in (manifest.get('assets') or {}).items():
        if bundle.startswith('web.assets_unit_tests'):
            continue
        yield bundle, entries


@tagged('post_install', '-at_install')
class TestPkAssets(TransactionCase):

    def test_kit_js_files_are_the_thirteen(self):
        root = os.path.join(get_module_path(KIT), 'static', 'src', 'js')
        found = sorted(os.path.basename(p)[3:-3] for p in glob.glob(os.path.join(root, 'pk_*.js')))
        self.assertEqual(found, sorted(KIT_JS))

    def test_each_kit_file_in_exactly_one_bundle(self):
        listings = {name: [] for name in KIT_JS}
        for module in get_modules():
            manifest = get_manifest(module)
            if not manifest:
                continue
            for bundle, entries in _runtime_bundles(manifest):
                for path in _asset_paths(entries):
                    for name in KIT_JS:
                        target = f'{KIT}/static/src/js/pk_{name}.js'
                        if fnmatch.fnmatch(target, path):
                            listings[name].append((module, bundle))
        for name, where in listings.items():
            self.assertEqual(where, [(KIT, 'web.assets_frontend')], f'pk_{name}.js')

    def test_unit_tests_are_bundled(self):
        tests = get_manifest(KIT)['assets']['web.assets_unit_tests']
        self.assertIn(f'{KIT}/static/tests/**/*', tests)

    def test_no_shim_left(self):
        shims = []
        for module in get_modules():
            manifest = get_manifest(module)
            if not manifest or module == KIT:
                continue
            for _bundle, entries in _runtime_bundles(manifest):
                for path in _asset_paths(entries):
                    if not path.endswith('.js') or '*' in path:
                        continue
                    try:
                        with file_open(path) as f:
                            source = f.read()
                    except (FileNotFoundError, ValueError):
                        continue
                    if SHIM_MARKER in source:
                        shims.append(path)
        self.assertEqual(shims, [])
        clinic = get_module_path('bemade_sports_clinic', display_warning=False)
        if clinic:
            left = [
                name for name in CLINIC_SHIMS
                if os.path.exists(os.path.join(clinic, 'static', 'src', 'js', f'sc_{name}.js'))
            ]
            self.assertEqual(left, [])
