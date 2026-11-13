# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5369 (kit P3c1): view xmlid adoption (``tools/adopt.py``).

* UC-A1 ``adopt_views`` gives an old consumer view the kit's external id and
  key: same ``ir.ui.view`` record (``res_id``), so its inheriting views and
  translations stay; a ``t-call`` of the new name renders it, the old name
  is gone.
* UC-A2 It is idempotent: a second call (the other module's pre-migration)
  adopts nothing; a view whose kit external id exists already is left alone;
  a missing old view is skipped.
* UC-A3 After the upgrade no ``<consumer>.<old name>`` row of the mapping is
  left, and every ``bemade_portal_kit.<new name>`` row exists (a view).
* UC-A4 The kit's views name no consumer: no ``o_sc_`` class, no
  ``data-sc-`` attribute, no ``bemade_sports_clinic.`` reference.
* UC-A5 (task 5372) The kit adopts at INSTALL too: the manifest declares a
  ``pre_init_hook`` that adopts the views of ``ADOPTED_VIEWS`` (a database
  with the consumer but not the kit installs the kit as a new dependency,
  and an installed module runs no migration script).
* UC-A7 (task 5370, P4b) The kit adopts two more templates: the form
  guard's slots and the status pill select (11 in all).
* UC-A9 (task 5381, P4c2) The kit adopts four more templates: the edit
  card head, the display row, the sheet and the page tabs (15 in all).
* UC-A8 (task 5370) ``strip_translated_attributes`` removes renamed
  attributes that a translation kept: Odoo merges the source's attributes
  into a translated term but never drops the term's own, so after a rename
  the old attribute stays, dead, in every non-English ``arch_db`` value.
  The source (``en_US``) is left alone and other attributes are kept.
* UC-A6 (task 5372) When both the kit's external id and the old consumer
  external id exist, ``adopt_views`` changes nothing but logs a WARNING
  naming both, so a broken upgrade path shows in the log. An already
  adopted view (old external id gone) logs no warning.
Synthetic views only (module ``pk_test_consumer``).
"""
import os
import re
from unittest.mock import patch

from psycopg2.extras import Json

from odoo.modules.module import get_manifest, get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons import bemade_portal_kit
from odoo.addons.bemade_portal_kit.tools import adopt
from odoo.addons.bemade_portal_kit.tools.adopt import (
    ADOPTED_VIEWS, KIT, adopt_views, strip_translated_attributes,
)

CONSUMER = 'pk_test_consumer'


@tagged('post_install', '-at_install')
class TestPkAdopt(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.view = cls.env['ir.ui.view'].create({
            'name': 'pk test: old view',
            'type': 'qweb',
            'key': '%s.pk_test_old' % CONSUMER,
            'arch': '<t t-name="pk_test_old"><b class="pk_test_adopted">adopted</b></t>',
        })
        cls.env['ir.model.data'].create({
            'module': CONSUMER, 'name': 'pk_test_old', 'model': 'ir.ui.view', 'res_id': cls.view.id,
        })
        cls.child = cls.env['ir.ui.view'].create({
            'name': 'pk test: inheriting view',
            'type': 'qweb',
            'inherit_id': cls.view.id,
            'arch': '<xpath expr="//b" position="after"><i>child</i></xpath>',
        })
        cls.mapping = ((CONSUMER, 'pk_test_old', 'pk_test_new'),)

    def _imd(self, module, name):
        return self.env['ir.model.data'].search([('module', '=', module), ('name', '=', name)])

    def test_adopts_and_keeps_the_record(self):
        adopted = adopt_views(self.env.cr, self.mapping)
        self.env.invalidate_all()
        self.assertEqual(adopted, [('%s.pk_test_old' % CONSUMER, '%s.pk_test_new' % KIT, self.view.id)])
        self.assertFalse(self._imd(CONSUMER, 'pk_test_old'))
        new = self._imd(KIT, 'pk_test_new')
        self.assertEqual((new.model, new.res_id), ('ir.ui.view', self.view.id))
        self.assertEqual(self.view.key, '%s.pk_test_new' % KIT)
        self.assertEqual(self.env.ref('%s.pk_test_new' % KIT), self.view)
        self.assertEqual(self.child.inherit_id, self.view)
        html = str(self.env['ir.qweb']._render('%s.pk_test_new' % KIT, {}))
        self.assertIn('pk_test_adopted', html)
        self.assertIn('<i>child</i>', html)

    def test_idempotent(self):
        self.assertTrue(adopt_views(self.env.cr, self.mapping))
        self.assertEqual(adopt_views(self.env.cr, self.mapping), [])
        self.env.invalidate_all()
        self.assertEqual(self.view.key, '%s.pk_test_new' % KIT)

    def test_kit_row_exists_left_alone(self):
        other = self.env['ir.ui.view'].create({
            'name': 'pk test: kit view', 'type': 'qweb', 'key': '%s.pk_test_new' % KIT,
            'arch': '<t t-name="pk_test_new"><b>kit</b></t>',
        })
        self.env['ir.model.data'].create({
            'module': KIT, 'name': 'pk_test_new', 'model': 'ir.ui.view', 'res_id': other.id,
        })
        with self.assertLogs(adopt._logger, 'WARNING') as logs:
            self.assertEqual(adopt_views(self.env.cr, self.mapping), [])
        self.env.invalidate_all()
        self.assertEqual(self._imd(CONSUMER, 'pk_test_old').res_id, self.view.id)
        self.assertEqual(self.view.key, '%s.pk_test_old' % CONSUMER)
        self.assertEqual(self.view.exists(), self.view)
        # UC-A6: the warning names both external ids and both view ids.
        self.assertEqual(len(logs.records), 1)
        message = logs.records[0].getMessage()
        for part in ('%s.pk_test_old' % CONSUMER, '%s.pk_test_new' % KIT, str(self.view.id), str(other.id)):
            self.assertIn(part, message)

    def test_already_adopted_no_warning(self):
        self.assertTrue(adopt_views(self.env.cr, self.mapping))
        with self.assertNoLogs(adopt._logger, 'WARNING'):
            self.assertEqual(adopt_views(self.env.cr, self.mapping), [])

    def test_install_hook_adopts(self):
        manifest = get_manifest(KIT)
        self.assertEqual(manifest.get('pre_init_hook'), 'pre_init_hook')
        hook = getattr(bemade_portal_kit, manifest['pre_init_hook'])
        with patch.object(adopt, 'ADOPTED_VIEWS', self.mapping):
            hook(self.env)
        self.env.invalidate_all()
        self.assertFalse(self._imd(CONSUMER, 'pk_test_old'))
        new = self._imd(KIT, 'pk_test_new')
        self.assertEqual((new.model, new.res_id), ('ir.ui.view', self.view.id))
        self.assertEqual(self.view.key, '%s.pk_test_new' % KIT)
        self.assertEqual(self.child.inherit_id, self.view)
        # A second run (an install hook after a migration) finds nothing to do.
        with patch.object(adopt, 'ADOPTED_VIEWS', self.mapping), self.assertNoLogs(adopt._logger, 'WARNING'):
            hook(self.env)

    def test_missing_old_view_skipped(self):
        self.assertEqual(adopt_views(self.env.cr, ((CONSUMER, 'pk_test_absent', 'pk_test_absent_new'),)), [])
        self.assertFalse(self._imd(KIT, 'pk_test_absent_new'))

    def test_strip_translated_attributes(self):
        self.env.cr.execute("UPDATE ir_ui_view SET arch_db = %s WHERE id = %s", (Json({
            'en_US': '<t t-name="pk_test_old"><span data-pk-old-msg="en" data-pk-test-msg="a">Text</span></t>',
            'fr_FR': '<t t-name="pk_test_old"><span data-pk-old-msg="a" data-pk-test-msg="a" class="x">Texte</span></t>',
            'fr_CA': '<t t-name="pk_test_old"><span data-pk-test-msg="a">Texte</span></t>',
        }), self.view.id))
        count = strip_translated_attributes(self.env.cr, ('data-pk-old-msg',))
        self.assertEqual(count, 1)
        self.env.cr.execute("SELECT arch_db FROM ir_ui_view WHERE id = %s", (self.view.id,))
        arch = self.env.cr.fetchone()[0]
        self.assertIn('data-pk-old-msg="en"', arch['en_US'], 'the source is left alone')
        self.assertEqual(arch['fr_FR'], '<t t-name="pk_test_old"><span data-pk-test-msg="a" class="x">Texte</span></t>')
        self.assertEqual(arch['fr_CA'], '<t t-name="pk_test_old"><span data-pk-test-msg="a">Texte</span></t>')
        self.assertEqual(strip_translated_attributes(self.env.cr, ('data-pk-old-msg',)), 0)

    def test_mapping_adopted_after_upgrade(self):
        self.assertEqual(len(ADOPTED_VIEWS), 15)
        for old, new in (('sc_edit_card_head', 'pk_edit_card_head'), ('sc_display_row', 'pk_display_row'),
                         ('sc_sheet', 'pk_sheet'), ('sc_page_tabs', 'pk_page_tabs')):
            self.assertIn(('bemade_sports_clinic', old, new), ADOPTED_VIEWS)
        self.assertIn(('bemade_sports_clinic', 'sc_form_guard_slots', 'pk_form_guard_slots'), ADOPTED_VIEWS)
        self.assertIn(('bemade_sports_clinic', 'sc_status_pill_select', 'pk_status_pill_select'), ADOPTED_VIEWS)
        for old_module, old_name, new_name in ADOPTED_VIEWS:
            with self.subTest(view=new_name):
                self.assertFalse(self._imd(old_module, old_name), '%s.%s left behind' % (old_module, old_name))
                new = self._imd(KIT, new_name)
                self.assertEqual(new.model, 'ir.ui.view')
                self.assertEqual(self.env['ir.ui.view'].browse(new.res_id).key, '%s.%s' % (KIT, new_name))

    def test_kit_views_name_no_consumer(self):
        root = get_module_path(KIT)
        pattern = re.compile(r'o_sc_|data-sc-|bemade_sports_clinic\.')
        hits = []
        for dirpath in (os.path.join(root, 'views'), os.path.join(root, 'static', 'src')):
            for base, _dirs, files in os.walk(dirpath):
                for filename in files:
                    if not filename.endswith('.xml'):
                        continue
                    path = os.path.join(base, filename)
                    with open(path, encoding='utf-8') as f:
                        for lineno, line in enumerate(f, 1):
                            if pattern.search(line):
                                hits.append('%s:%s' % (os.path.relpath(path, root), lineno))
        self.assertFalse(hits, 'kit views naming a consumer:\n' + '\n'.join(hits))
        arch = self.env['ir.ui.view'].search([('key', '=like', KIT + '.%')]).mapped('arch_db')
        self.assertFalse([a for a in arch if pattern.search(a or '')])
