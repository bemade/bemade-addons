# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5370 (kit P4b): the form guard, the status pills and the lazy edit
move to the kit.

* UC-G1 ``PK_GUARD_HEADER`` (``tools``) is ``X-Pk-Guard``; the header a
  guarded form's fetch sends. ``PortalKitApp._pk_guard_probe()`` is True
  only for a request carrying it with ``1``, False without a request.
* UC-G2 ``bemade_portal_kit.pk_form_guard_slots`` renders the error slot and
  the reason line (``data-pk-guard-error``, ``data-pk-guard-reason``,
  ``o_pk_guard_reason``, id ``<guard_id>_reason``).
* UC-G3 ``bemade_portal_kit.pk_status_pill_select`` renders an editable pill
  with its ``data-pk-*`` target and items, its menu id prefixed ``pk-pill-``,
  and a read-only pill (``data-pk-pill-readonly``).
* UC-G4 The three scripts are the kit's, in its runtime bundle and in the
  hoot test setup.
Synthetic fixtures only.
"""
from unittest.mock import MagicMock, patch

from lxml import html as lxml_html

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit import tools as pk_tools
from odoo.addons.bemade_portal_kit.controllers import pk_app
from odoo.addons.bemade_portal_kit.controllers.pk_app import PortalKitApp

KIT = 'bemade_portal_kit'
SCRIPTS = ('pk_form_guard', 'pk_status_pills', 'pk_lazy_edit')


def _fake_request(headers):
    fake = MagicMock()
    fake.httprequest.headers = headers
    return fake


@tagged('post_install', '-at_install')
class TestPkGuard(TransactionCase):

    def _render(self, template, values):
        return lxml_html.fragment_fromstring(
            str(self.env['ir.qweb']._render(template, values)), create_parent='div')

    def test_header_constant(self):
        self.assertEqual(pk_tools.PK_GUARD_HEADER, 'X-Pk-Guard')

    def test_probe(self):
        with patch.object(pk_app, 'request', _fake_request({'X-Pk-Guard': '1'})):
            self.assertTrue(PortalKitApp._pk_guard_probe())
        with patch.object(pk_app, 'request', _fake_request({'X-Pk-Guard': '0'})):
            self.assertFalse(PortalKitApp._pk_guard_probe())
        with patch.object(pk_app, 'request', _fake_request({'X-Sc-Guard': '1'})):
            self.assertFalse(PortalKitApp._pk_guard_probe())
        # No request at all (a cron, a shell): False, no error.
        self.assertFalse(PortalKitApp._pk_guard_probe())

    def test_guard_slots(self):
        root = self._render('%s.pk_form_guard_slots' % KIT, {'guard_id': 'pk_t_form'})
        error = root.xpath('.//*[@data-pk-guard-error]')
        reason = root.xpath('.//*[@data-pk-guard-reason]')
        self.assertEqual(len(error), 1)
        self.assertEqual(error[0].get('role'), 'alert')
        self.assertEqual(len(reason), 1)
        self.assertEqual(reason[0].get('id'), 'pk_t_form_reason')
        self.assertIn('o_pk_guard_reason', reason[0].get('class'))
        self.assertNotIn('data-sc-', lxml_html.tostring(root, encoding='unicode'))

    def _pill(self):
        return {
            'key': 'state', 'value': 'a', 'tone': 'green', 'icon': False, 'title': 'State: A',
            'text': 'State: A', 'label': 'State', 'menu_label': 'State',
            'target': {'model': 'x.thing', 'id': 7, 'field': 'state',
                       'write_date': '2026-01-01 10:00:00', 'old_value': 'a'},
            'options': [
                {'value': 'a', 'label': 'A', 'tone': 'green', 'checked': True, 'disabled': False},
                {'value': 'b', 'label': 'B', 'tone': 'red', 'checked': False, 'disabled': True,
                 'hint': 'Not now'},
                {'value': 'c', 'label': 'C', 'tone': 'secondary', 'checked': False, 'disabled': False,
                 'action': 'thing.verify', 'from': 'a'},
            ],
        }

    def test_pill_editable(self):
        root = self._render('%s.pk_status_pill_select' % KIT, {
            'pill': self._pill(), 'editable': True, 'compact': False, 'scope': 'row',
            'undo_message': 'State changed',
        })
        wrap = root.xpath('.//*[@data-pk-pill-select]')
        self.assertEqual(len(wrap), 1)
        wrap = wrap[0]
        self.assertEqual(wrap.get('data-pk-pill-key'), 'state')
        self.assertEqual(wrap.get('data-pk-model'), 'x.thing')
        self.assertEqual(wrap.get('data-pk-record-id'), '7')
        self.assertEqual(wrap.get('data-pk-field'), 'state')
        self.assertEqual(wrap.get('data-pk-write-date'), '2026-01-01 10:00:00')
        self.assertEqual(wrap.get('data-pk-old-value'), 'a')
        self.assertEqual(wrap.get('data-pk-undo-message'), 'State changed')
        popup = wrap.xpath('.//*[@data-pk-menu-popup]')[0]
        self.assertEqual(popup.get('id'), 'pk-pill-x-thing-7-state-row')
        items = wrap.xpath('.//*[@role="menuitemradio"]')
        self.assertEqual([i.get('data-pk-pill-value') for i in items], ['a', 'b', 'c'])
        self.assertEqual(items[0].get('data-pk-pill-post'), 'a')
        self.assertIsNone(items[1].get('data-pk-pill-post'))
        self.assertEqual(items[1].get('aria-disabled'), 'true')
        self.assertEqual(items[2].get('data-pk-pill-action'), 'thing.verify')
        self.assertEqual(items[2].get('data-pk-pill-from'), 'a')
        self.assertNotIn('data-sc-', lxml_html.tostring(root, encoding='unicode'))

    def test_pill_readonly(self):
        root = self._render('%s.pk_status_pill_select' % KIT, {
            'pill': self._pill(), 'editable': False, 'compact': False, 'scope': False,
            'undo_message': False,
        })
        self.assertFalse(root.xpath('.//*[@data-pk-pill-select]'))
        pill = root.xpath('.//*[@data-pk-pill-readonly]')
        self.assertEqual(len(pill), 1)
        self.assertEqual(pill[0].get('data-pk-pill-key'), 'state')

    def test_scripts_bundled(self):
        assets = get_manifest(KIT)['assets']
        for name in SCRIPTS:
            path = '%s/static/src/js/%s.js' % (KIT, name)
            self.assertIn(path, assets['web.assets_frontend'])
            self.assertIn(path, assets['web.assets_unit_tests_setup'])
