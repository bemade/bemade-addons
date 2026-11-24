# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: an internal user reaches every portal user in Discuss.

Acceptance criteria:

* UC-B1 ``res.partner._search_for_channel_invite`` (the « start a
  conversation » search and the invite dialog) returns portal partners
  (and internal ones) for an internal user.
* UC-B2 For a share user it stays the core's (internal users only).
* UC-B3 An internal user's Discuss sees a portal user's message in their
  direct chat (the chat is a native Discuss channel).
* UC-B4 The back end loads with the palette and avatar card patches (no
  JS error; the patch module is defined).
Synthetic users only.
"""
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.mail.tools.discuss import Store

from .common import enter, pk_chat_people, pk_chat_shell


@tagged('post_install', '-at_install')
class TestPkChatBackend(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_chat_people(cls)

    def _search(self, user, term='Testperson'):
        return self.env['res.partner'].with_user(user)._search_for_channel_invite(Store(), term)['partner_ids']

    # UC-B1
    def test_internal_finds_portal(self):
        found = self._search(self.dana)
        self.assertIn(self.avery.partner_id.id, found)
        self.assertIn(self.blake.partner_id.id, found)
        self.assertIn(self.dana.partner_id.id, self._search(self.env.ref('base.user_admin'), 'Staffperson'))

    # UC-B2
    def test_share_keeps_core(self):
        self.assertNotIn(self.blake.partner_id.id, self._search(self.avery))

    # UC-B3
    def test_internal_sees_portal_message(self):
        enter(self, pk_chat_shell(self.env, contacts=lambda kit, user: self.dana.partner_id))
        channel = self.env['portal.kit'].with_user(self.avery).pk_chat_start(self.dana.partner_id.id)
        channel.with_user(self.avery).sudo().message_post(
            body='Question about Saturday', message_type='comment', subtype_xmlid='mail.mt_comment')
        dana_channels = self.env['discuss.channel'].with_user(self.dana).search([('is_member', '=', True),
                                                                                  ('channel_type', '=', 'chat')])
        self.assertIn(channel, dana_channels)
        bodies = channel.with_user(self.dana).message_ids.mapped('body')
        self.assertTrue(any('Question about Saturday' in str(b) for b in bodies))


@tagged('post_install', '-at_install')
class TestPkChatBackendAssets(HttpCase):

    # UC-B4
    def test_backend_loads_with_patches(self):
        code = """
            const mod = odoo.loader.modules.get('@bemade_portal_kit_chat/backend/pk_chat_palette');
            const pure = odoo.loader.modules.get('@bemade_portal_kit_chat/backend/pk_chat_portal_partners');
            if (mod && pure && pure.pkPortalPartners) {
                console.log('test successful');
            } else {
                console.error('the chat backend patches are not loaded');
            }
        """
        self.browser_js('/odoo/discuss', code, ready="odoo.isReady", login='admin', timeout=120)
