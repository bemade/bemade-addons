# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5382 (kit P4c3): the autosave field.

* UC-A1 ``tools/field_props.py`` (pure functions) builds the JSON props of
  the kit's autosave field (``bemade_portal_kit.pk_autosave_field``):
  ``pk_field_props(record, field, label, input_type, **extra)`` (server
  mode: the value and write date the save route compares against),
  ``pk_draft_props(draft_key, name, label, ...)`` (draft mode: the draft
  key is the caller's, verbatim, so drafts kept on devices survive),
  ``pk_form_props(target, label, ...)`` (form mode) and
  ``pk_options(pairs)``. Texts become strings, ``None`` extras are dropped,
  input ids take the ``pk_`` / ``pk_draft_`` prefixes.
* UC-A2 The adopted template ``bemade_portal_kit.pk_field_autosave``
  renders the component's ``<owl-component>`` with the kit alone.
* UC-A3 The component's script and template are bundled (frontend and unit
  tests); its styles (the replace editor and the group confirm) are the
  kit's.
Synthetic data only.
"""
import json
import re
from unittest.mock import MagicMock

from lxml import html as lxml_html
from markupsafe import Markup

from odoo import fields
from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit.controllers.pk_app import PortalKitApp
from odoo.addons.bemade_portal_kit.tools import field_props as pk_field_props_tools
from odoo.addons.bemade_portal_kit.tools import pk_draft_props, pk_field_props, pk_form_props, pk_options

KIT = 'bemade_portal_kit'
OWL_KEY = 'bemade_portal_kit.pk_autosave_field'


@tagged('post_install', '-at_install')
class TestPkAutosave(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Pk Test Person', 'email': 'pk.t@example.com'})

    # ------------------------------------------------------------- UC-A1
    def test_options(self):
        self.assertEqual(pk_options([(1, 'One'), ('', 'None')]), [['1', 'One'], ['', 'None']])
        # A tags option may carry its group: (key, label, group label, group key).
        self.assertEqual(pk_options([(3, 'Three', 'Odd', 1)]), [['3', 'Three', 'Odd', '1']])
        self.assertEqual(pk_options(()), [])

    def test_field_props(self):
        props = json.loads(pk_field_props(self.partner, 'name', 'Name'))
        self.assertEqual(props, {
            'mode': 'server',
            'model': 'res.partner',
            'recordId': self.partner.id,
            'field': 'name',
            'writeDate': fields.Datetime.to_string(self.partner.write_date),
            'label': 'Name',
            'inputType': 'text',
            'inputId': 'pk_res_partner_%s_name' % self.partner.id,
            'value': 'Pk Test Person',
        })
        # The value is the save route's (a many2one's id, '' read as False).
        self.partner.country_id = self.env.ref('base.ca')
        props = json.loads(pk_field_props(self.partner, 'country_id', 'Country', 'select',
                                          options=[(self.env.ref('base.ca').id, 'Canada')]))
        self.assertEqual(props['value'], PortalKitApp._pk_save_value(self.partner, 'country_id'))
        self.assertEqual(props['value'], self.env.ref('base.ca').id)
        self.assertEqual(props['options'], [[str(self.env.ref('base.ca').id), 'Canada']])
        self.assertEqual(props['inputType'], 'select')

    def test_field_props_extras(self):
        props = json.loads(pk_field_props(
            self.partner, 'comment', 'Comment', 'textarea', hint=None, clearable=True, replace=True,
            savedLabel=Markup('Sent'), replaceNewLabel='New text', groupConfirmMessage='Drop %s?', inputId='pk_t_own'))
        self.assertNotIn('hint', props)
        self.assertIs(props['clearable'], True)
        self.assertIs(props['replace'], True)
        self.assertEqual(props['savedLabel'], 'Sent')
        self.assertEqual(props['replaceNewLabel'], 'New text')
        self.assertEqual(props['groupConfirmMessage'], 'Drop %s?')
        # A caller's own input id wins.
        self.assertEqual(props['inputId'], 'pk_t_own')

    def test_draft_props(self):
        props = json.loads(pk_draft_props('thing:new:7:summary', 'summary', 'Summary', 'textarea', value='Hi',
                                          placeholder='Type…', options=None))
        self.assertEqual(props, {
            'mode': 'draft',
            'name': 'summary',
            'draftKey': 'thing:new:7:summary',  # the caller's key, verbatim
            'label': 'Summary',
            'inputType': 'textarea',
            'inputId': 'pk_draft_summary',
            'value': 'Hi',
            'placeholder': 'Type…',
        })
        self.assertEqual(json.loads(pk_draft_props('k', 'n', 'L'))['value'], '')

    def test_form_props(self):
        props = json.loads(pk_form_props('pk_t_target', 'Groups', value='1,2',
                                         options=[(1, 'A', 'G', 'g'), (2, 'B', 'G', 'g')],
                                         groupSelect='pk_t_group', groupConfirmLabel='Switch'))
        self.assertEqual(props['mode'], 'form')
        self.assertEqual(props['target'], 'pk_t_target')
        self.assertEqual(props['inputType'], 'tags')
        self.assertEqual(props['inputId'], 'pk_t_target_field')
        self.assertEqual(props['value'], '1,2')
        self.assertEqual(props['options'], [['1', 'A', 'G', 'g'], ['2', 'B', 'G', 'g']])
        self.assertEqual(props['groupSelect'], 'pk_t_group')
        self.assertEqual(props['groupConfirmLabel'], 'Switch')

    def test_field_props_module_is_pure(self):
        for name, value in vars(pk_field_props_tools).items():
            if not name.startswith('__'):
                self.assertNotIsInstance(value, (dict, list, set), name)

    # ------------------------------------------------------------- UC-A2
    def _render(self, values):
        fake = MagicMock()
        fake.csrf_token.return_value = 'pk-t-token'
        values = dict(values, request=fake)
        out = self.env['ir.qweb'].with_context(minimal_qcontext=True)._render(
            '%s.pk_field_autosave' % KIT, values)
        return lxml_html.fragment_fromstring(str(out), create_parent='div')

    def test_template_renders_kit_only(self):
        view = self.env.ref('%s.pk_field_autosave' % KIT)
        self.assertEqual(view.key, '%s.pk_field_autosave' % KIT)
        props = pk_field_props(self.partner, 'name', 'Name')
        root = self._render({'props': props})
        component = root.xpath('.//owl-component')
        self.assertEqual(len(component), 1)
        self.assertEqual(component[0].get('name'), OWL_KEY)
        self.assertEqual(json.loads(component[0].get('props')), json.loads(props))
        markup = lxml_html.tostring(root, encoding='unicode')
        self.assertNotRegex(markup, re.compile(r'data-sc-|o_sc_|sc_'))

    # ------------------------------------------------------------- UC-A3
    def test_assets(self):
        assets = get_manifest(KIT)['assets']
        for path in ('%s/static/src/js/pk_autosave_field.js' % KIT, '%s/static/src/js/pk_autosave_field.xml' % KIT):
            self.assertIn(path, assets['web.assets_frontend'])
            self.assertIn(path, assets['web.assets_unit_tests_setup'])

    def test_styles(self):
        bundle = self.env['ir.qweb']._get_asset_bundle('web.assets_frontend', js=False)
        css = re.sub(r'\s+', ' ', bundle.css().raw.decode())
        self.assertFalse(bundle.css_errors, bundle.css_errors)
        for selector in ('.o_pk_app .o_pk_replace_current', '.o_pk_app .o_pk_replace_current_text',
                         '.o_pk_app .o_pk_replace_caption', '.o_pk_app .o_pk_replace_new_head',
                         '.o_pk_app .o_pk_replace_hint', '.o_pk_app .o_pk_group_confirm',
                         '.o_pk_app .o_pk_group_confirm .o_pk_group_confirm_text',
                         '.o_pk_app .o_pk_group_confirm .o_pk_group_confirm_actions',
                         '.o_pk_app .o_pk_replace_new_head .o_pk_replace_reuse'):
            self.assertRegex(css, re.escape(selector) + r' ?[{,]', selector)
