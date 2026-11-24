# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5202 (kit P7): static checks of the dashboard addon.

* UC-S1 Assets: the configure script, the anchoring and the stylesheet in
  web.assets_frontend; the scripts and their hoot tests in the unit test
  bundles. The configure script reads the move route from the page
  (data-pk-dash-move-url), never a hard-coded URL.
* UC-S2 Community only: depends on the kit alone; LGPL-3.
* UC-S3 This addon names no consumer (outside the adoption mapping) and
  holds no mutable module-level container.
"""
import os

from odoo.modules.module import get_manifest, get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open

from odoo.addons.bemade_portal_kit_dashboard import hooks
from odoo.addons.bemade_portal_kit_dashboard.controllers import pk_dashboard as dash_controller
from odoo.addons.bemade_portal_kit_dashboard.models import portal_kit as dash_kit
from odoo.addons.bemade_portal_kit_dashboard.models import portal_kit_dashboard as dash_model
from odoo.addons.bemade_portal_kit_dashboard.tools import adopt as dash_adopt

DASH = 'bemade_portal_kit_dashboard'
CONFIG_JS = DASH + '/static/src/js/pk_dashboard_config.js'
ANCHOR_JS = DASH + '/static/src/js/pk_dashboard_anchor.js'
SCSS = DASH + '/static/src/scss/pk_dashboard.scss'


@tagged('post_install', '-at_install')
class TestPkDashboardStatic(TransactionCase):

    def test_assets(self):
        manifest = get_manifest(DASH)
        assets = manifest['assets']
        self.assertEqual(assets['web.assets_frontend'], [SCSS, CONFIG_JS, ANCHOR_JS])
        self.assertEqual(assets['web.assets_unit_tests_setup'], [CONFIG_JS, ANCHOR_JS])
        with file_open(CONFIG_JS) as source:
            config = source.read()
        self.assertIn('root.dataset.pkDashMoveUrl', config)
        self.assertNotIn('"/my/app/dashboard', config)
        self.assertNotIn('data-sc-', config)
        with file_open(ANCHOR_JS) as source:
            self.assertIn('[data-pk-dashboard]', source.read())

    def test_community_only(self):
        manifest = get_manifest(DASH)
        self.assertEqual(manifest['depends'], ['bemade_portal_kit'])
        self.assertEqual(manifest['license'], 'LGPL-3')
        self.assertEqual(manifest['version'], '19.0.1.1.1')
        self.assertEqual(manifest['pre_init_hook'], 'pre_init_hook')

    def test_names_no_consumer(self):
        root = get_module_path(DASH)
        allowed = {os.path.join('tools', 'adopt.py'), os.path.join('tests', 'test_pk_dashboard_static.py'),
                   os.path.join('tests', 'test_pk_dashboard_migration.py')}
        hits = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ('__pycache__', 'description')]
            for filename in filenames:
                if not filename.endswith(('.py', '.js', '.xml', '.scss', '.po')):
                    continue
                path = os.path.join(dirpath, filename)
                rel = os.path.relpath(path, root)
                if rel in allowed:
                    continue
                with open(path, encoding='utf-8') as handle:
                    text = handle.read().lower().replace('language-team', '')
                for word in ('sports_clinic', 'fit crew', 'fitcrew', 'sports.', 'patient', 'team', 'player',
                             'injur', 'therapist', 'coach', 'organi', 'activit'):
                    if word in text:
                        hits.append('%s: %s' % (rel, word))
        self.assertFalse(hits)

    def test_no_mutable_module_state(self):
        for module in (dash_model, dash_kit, dash_controller, dash_adopt, hooks):
            for name, value in vars(module).items():
                if not name.startswith('__'):
                    self.assertNotIsInstance(value, (dict, list, set), '%s.%s' % (module.__name__, name))
