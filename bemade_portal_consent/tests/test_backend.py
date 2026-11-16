# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Back office.

Acceptance criteria
-------------------
* A consent manager creates a document and a draft version through the
  forms.
* The « Publish » wizard publishes a draft with or without « Require a new
  acceptance »; on the first version of a document the box is forced.
* A document's pending users are exactly the portal users whose hook
  returns the document and who have not complied; the « Pending users »
  button opens them.
* The consent menus (Settings › Users & Companies) are restricted to the
  consent managers (administrators are consent managers), hidden from
  other internal users.
"""
from odoo.fields import Command
from odoo.tests import Form, TransactionCase, new_test_user, tagged

from .common import ConsentFixtures, consent_hook


@tagged('post_install', '-at_install')
class TestConsentBackend(ConsentFixtures, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._consent_setup()
        cls.manager = new_test_user(
            cls.env, login='tc5390_manager',
            groups='base.group_user,bemade_portal_consent.group_portal_consent_manager')

    def _publish(self, version, requires_resign):
        action = version.action_open_publish_wizard()
        wizard_form = Form(self.env[action['res_model']].with_context(**action['context']))
        if not wizard_form.is_first:
            wizard_form.requires_resign = requires_resign
        wizard_form.save().action_confirm()

    def test_forms_as_manager(self):
        env = self.env(user=self.manager)
        with Form(env['portal.consent.document']) as doc_form:
            doc_form.name = 'Sample volunteer undertaking'
            doc_form.code = 'tc5390_volunteer'
        document = doc_form.record
        with Form(env['portal.consent.version']) as version_form:
            version_form.document_id = document
            version_form.body = '<p>Sample undertaking.</p>'
        version = version_form.record
        self.assertEqual((version.number, version.state), (1, 'draft'))
        self._publish(version.with_env(env), requires_resign=False)
        self.assertEqual(version.state, 'published')
        self.assertTrue(version.requires_resign, 'forced on the first version')

    def test_wizard_resign_choice(self):
        self._publish(self.v1, requires_resign=True)
        v2 = self._new_version('<p>Two.</p>')
        self._publish(v2, requires_resign=False)
        self.assertFalse(v2.requires_resign)
        v3 = self._new_version('<p>Three.</p>')
        self._publish(v3, requires_resign=True)
        self.assertTrue(v3.requires_resign)
        self.assertEqual(self.doc.required_version_id, v3)

    def test_pending_users(self):
        self.v1._portal_consent_publish(requires_resign=True)
        with consent_hook(self.env, lambda user: self.doc if user in self.portal_a | self.portal_b else
                          self.Document):
            self.assertEqual(self.doc._portal_consent_pending_users(), self.portal_a | self.portal_b)
            self.v1._portal_consent_accept(self.portal_a)
            self.assertEqual(self.doc._portal_consent_pending_users(), self.portal_b)
            action = self.doc.action_view_pending_users()
            self.assertEqual(action['res_model'], 'res.users')
            self.assertEqual(self.env['res.users'].search(action['domain']), self.portal_b)

    def test_menu_visibility(self):
        Menu = self.env['ir.ui.menu']
        group = self.env.ref('bemade_portal_consent.group_portal_consent_manager')
        self.assertTrue(group in self.env.ref('base.group_system').all_implied_ids, 'admins manage consents')
        for xmlid in ('menu_portal_consent_document', 'menu_portal_consent_acceptance'):
            menu = self.env.ref('bemade_portal_consent.%s' % xmlid)
            self.assertEqual(menu.group_ids, group)
            self.assertNotIn(menu.id, Menu.with_user(self.staff)._visible_menu_ids())
            # Under Settings, a manager also needs to see Settings (consumers can
            # add their own menu entry on the same actions).
            self.manager.group_ids = [Command.link(self.env.ref('base.group_erp_manager').id)]
            self.assertIn(menu.id, Menu.with_user(self.manager)._visible_menu_ids())
