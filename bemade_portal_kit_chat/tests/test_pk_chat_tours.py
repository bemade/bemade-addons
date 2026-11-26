# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: browser tours of the portal chat (static/tests/tours/).

Acceptance criteria:

* UC-T1 A portal user opens the bubble, starts a chat with a contact (the
  kit's picker) and sends; the internal user sees the message in their
  Discuss chat (server-side assert).
* UC-T2 A portal reader of an announcement group has no composer and no
  member list; « Reply » on the announcement sends a reply that shows its
  quote; the poster sees the reply in Discuss.
* UC-T3 The open window follows the user to the next page.
Synthetic users only.
"""
from odoo.tests import HttpCase, tagged

from odoo.addons.bemade_portal_kit.tests.common import pk_frontend_langs

from .common import enter, pk_chat_people, pk_chat_shell


@tagged('post_install', '-at_install')
class TestPkChatTours(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        pk_chat_people(cls)

    def setUp(self):
        super().setUp()
        self.specs = [{'key': 'tour-1', 'name': 'Team Tour parents', 'members': {
            self.dana.partner_id.id: 'poster', self.avery.partner_id.id: 'reader',
            self.blake.partner_id.id: 'reader'}}]
        enter(self, pk_chat_shell(
            self.env, managed=lambda kit: self.specs,
            contacts=lambda kit, user: kit.env['res.partner'].sudo().search(
                [('user_ids.login', 'in', ('pkc_dana', 'pkc_blake'))]) - user.partner_id))

    # UC-T1
    def test_start_and_send(self):
        self.start_tour('/my/app/more', 'pk_chat_start_and_send', login='pkc_avery')
        chat = self.env['discuss.channel'].with_user(self.dana).search(
            [('channel_type', '=', 'chat'), ('is_member', '=', True)])
        chat = chat.filtered(lambda c: self.avery.partner_id in c.sudo().channel_member_ids.partner_id)
        self.assertEqual(len(chat), 1)
        bodies = [str(b) for b in chat.with_user(self.dana).message_ids.mapped('body')]
        self.assertTrue(any('Hello from the tour' in b for b in bodies), bodies)

    # UC-T2
    def test_reply_to_announcement(self):
        self.env['portal.kit']._pk_chat_sync()
        group = self.env['discuss.channel'].search([('pk_managed_key', '=', 'tour-1')])
        news = group.with_user(self.dana).message_post(body='Practice moved to 6 pm', message_type='comment',
                                                       subtype_xmlid='mail.mt_comment')
        self.start_tour('/my/app/more', 'pk_chat_reply_announcement', login='pkc_avery')
        reply = group.with_user(self.dana).message_ids.filtered(lambda m: m.parent_id == news)
        self.assertEqual(reply.author_id, self.avery.partner_id)

    # UC-T3
    def test_window_follows(self):
        channel = self.env['portal.kit'].with_user(self.avery).pk_chat_start(self.dana.partner_id.id)
        channel.with_user(self.dana).message_post(body='Hello again', message_type='comment',
                                                  subtype_xmlid='mail.mt_comment')
        self.start_tour('/my/app/more', 'pk_chat_window_follows', login='pkc_avery')
