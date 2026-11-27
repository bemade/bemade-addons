# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5201 (kit P6): static checks of the installable app.

* UC-S1 The page script registers ``/my/service-worker.js`` with scope
  ``/`` inside the shell (``.o_pk_app[data-pk-app-shell]``) only; the kill
  switch finds every registration of the worker by its script URL,
  whatever its scope. Markers ``data-pk-sw`` / ``data-pk-install-*``.
* UC-S2 Assets: the page script in ``web.assets_frontend`` (not in the
  lazy bundle), the worker never bundled.
* UC-S3 This addon names no consumer (outside the adoption mapping) and
  holds no mutable module-level container.
* UC-S4 Adoption: the install hook gives the first consumer's two views
  this addon's external ids, keeping their ids; idempotent; a no-op
  without them.
"""
import os

from odoo.modules.module import get_manifest, get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open, file_path

from odoo.addons.bemade_portal_kit.tools.adopt import adopt_views
from odoo.addons.bemade_portal_kit_pwa import hooks
from odoo.addons.bemade_portal_kit_pwa.controllers import pk_pwa as pwa_controller
from odoo.addons.bemade_portal_kit_pwa.models import portal_kit as pwa_model
from odoo.addons.bemade_portal_kit_pwa.tools import adopt as pwa_adopt

REGISTER_JS = 'bemade_portal_kit_pwa/static/src/js/pk_sw_register.js'


@tagged('post_install', '-at_install')
class TestPkPwaStatic(TransactionCase):

    @staticmethod
    def _register_source():
        with file_open(REGISTER_JS) as source:
            return source.read()

    # ------------------------------------------------------------- UC-S1
    def test_register_script(self):
        source = self._register_source()
        self.assertIn('export const PK_SW_URL = "/my/service-worker.js";', source)
        self.assertIn('export const PK_SW_SCOPE = "/";', source)
        self.assertIn('.register(PK_SW_URL, { scope: PK_SW_SCOPE })', source)
        self.assertIn('const SHELL = ".o_pk_app[data-pk-app-shell]";', source)
        self.assertNotIn('"/my/"', source)
        # Matched on the script URL, never on one scope.
        self.assertIn('getRegistrations()', source)
        self.assertRegex(source, r'new URL\(worker\.scriptURL\)\.pathname === PK_SW_URL')
        self.assertNotIn('reg.scope', source)
        self.assertIn('resp.status !== 404', source)
        for marker in ('data-pk-sw', 'data-pk-install', 'data-pk-install-state', 'data-pk-install-steps',
                       'data-pk-install-prompt'):
            self.assertIn(marker, source)
        self.assertNotIn('data-sc-', source)

    # ------------------------------------------------------------- UC-S2
    def test_assets(self):
        assets = get_manifest('bemade_portal_kit_pwa')['assets']
        # Task 5546: the phone notifications' page script.
        self.assertEqual(assets['web.assets_frontend'], [REGISTER_JS, 'bemade_portal_kit_pwa/static/src/js/pk_push.js'])
        self.assertNotIn('web.assets_frontend_lazy', assets)
        bundled = [path for paths in assets.values() for path in paths if isinstance(path, str)]
        self.assertFalse([path for path in bundled if '/sw/' in path])
        self.assertTrue(file_path(pwa_controller.PK_SW_SOURCE))

    # ------------------------------------------------------------- UC-S3
    def test_names_no_consumer(self):
        root = get_module_path('bemade_portal_kit_pwa')
        allowed = {os.path.join('tools', 'adopt.py'), os.path.join('tests', 'test_pk_pwa_static.py')}
        hits = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ('__pycache__', 'description')]
            for filename in filenames:
                if not filename.endswith(('.py', '.js', '.xml', '.css', '.po')):
                    continue
                path = os.path.join(dirpath, filename)
                rel = os.path.relpath(path, root)
                if rel in allowed:
                    continue
                with open(path, encoding='utf-8') as handle:
                    text = handle.read().lower()
                for word in ('sports_clinic', 'fit crew', 'fitcrew', 'sports.', 'patient'):
                    if word in text:
                        hits.append('%s: %s' % (rel, word))
        self.assertFalse(hits)

    def test_no_mutable_module_state(self):
        for module in (pwa_model, pwa_controller, pwa_adopt, hooks):
            for name, value in vars(module).items():
                if not name.startswith('__'):
                    self.assertNotIsInstance(value, (dict, list, set), '%s.%s' % (module.__name__, name))

    # ------------------------------------------------------------- UC-S4
    def test_adoption(self):
        cr = self.env.cr
        mapping = (('pk_p6_old', 'pk_p6_old_view', 'pk_p6_new_view'),)
        view = self.env['ir.ui.view'].create({
            'name': 'pk p6 old', 'type': 'qweb', 'key': 'pk_p6_old.pk_p6_old_view',
            'arch': '<t t-name="pk_p6_old.pk_p6_old_view"><div/></t>'})
        self.env['ir.model.data'].create({'module': 'pk_p6_old', 'name': 'pk_p6_old_view',
                                          'model': 'ir.ui.view', 'res_id': view.id})
        adopted = adopt_views(cr, mapping, target='bemade_portal_kit_pwa')
        self.assertEqual(adopted, [('pk_p6_old.pk_p6_old_view', 'bemade_portal_kit_pwa.pk_p6_new_view', view.id)])
        self.env.invalidate_all()
        self.assertEqual(self.env.ref('bemade_portal_kit_pwa.pk_p6_new_view'), view)
        self.assertEqual(view.key, 'bemade_portal_kit_pwa.pk_p6_new_view')
        self.assertEqual(adopt_views(cr, mapping, target='bemade_portal_kit_pwa'), [], 'idempotent')
        # The real mapping: the two templates are this addon's, whatever the
        # install path (a no-op here: already adopted or never there).
        self.assertEqual([new for _old, _name, new in pwa_adopt.PWA_ADOPTED_VIEWS],
                         ['pk_app_install', 'pk_app_offline'])
        hooks.pre_init_hook(self.env)
        for name in ('pk_app_install', 'pk_app_offline'):
            self.assertTrue(self.env.ref('bemade_portal_kit_pwa.%s' % name))
