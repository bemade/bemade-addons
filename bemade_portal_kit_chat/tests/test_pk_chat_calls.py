# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: no calls for share users.

Acceptance criteria:

* UC-K1 A share (portal) user can neither start nor join a call in a chat
  or a group (``/mail/rtc/channel/join_call``, the member's
  ``_rtc_join_call``): refused, no RTC session.
* UC-K2 An internal user still can (vanilla).
Synthetic users only.
"""
from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException
from odoo.tools.misc import mute_logger

from .common import enter, pk_chat_people, pk_chat_shell


@tagged('post_install', '-at_install')
class TestPkChatCalls(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_chat_people(cls)

    def setUp(self):
        super().setUp()
        enter(self, pk_chat_shell(self.env))
        self.chat = self.env['discuss.channel'].with_user(self.dana)._get_or_create_chat([self.avery.partner_id.id])

    def _member(self, user):
        return self.chat.channel_member_ids.filtered(lambda m: m.partner_id == user.partner_id)

    # UC-K1
    @mute_logger('odoo.http')
    def test_share_user_cannot_call(self):
        with self.assertRaises(UserError):
            self._member(self.avery).sudo()._rtc_join_call()
        self.authenticate('pkc_avery', 'pkc_avery')
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request('/mail/rtc/channel/join_call', {'channel_id': self.chat.id})
        self.assertFalse(self.env['discuss.channel.rtc.session'].search([('channel_id', '=', self.chat.id)]))

    # UC-K2
    def test_internal_user_can_call(self):
        self.authenticate('pkc_dana', 'pkc_dana')
        self.make_jsonrpc_request('/mail/rtc/channel/join_call', {'channel_id': self.chat.id})
        sessions = self.env['discuss.channel.rtc.session'].search([('channel_id', '=', self.chat.id)])
        self.assertEqual(sessions.channel_member_id.partner_id, self.dana.partner_id)
