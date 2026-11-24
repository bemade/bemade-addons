# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the managed channels' sync.

Acceptance criteria:

* UC-S1 A key the hook returns gets a ``group`` channel (its name, its
  ``pk_managed_key``, no ``group_public_id``) with exactly the hook's
  members and roles; a later sync adds and removes members, changes roles
  and renames the channel.
* UC-S2 Silent: no « joined » / « invited » message in the channel, ever.
* UC-S3 A key the hook no longer returns: the channel is archived (not
  deleted); returned again, it is active again.
* UC-S4 Idempotent: a second sync changes nothing (same channel, same
  members, no message).
* UC-S5 A newly synced member starts with the channel's history read and
  already « e-mailed » (high-water mark at the last message).
* UC-S6 ``key=`` syncs that channel only (and archives nothing).
Synthetic users only.
"""
from odoo.tests import TransactionCase, tagged

from .common import enter, pk_chat_people, pk_chat_shell


@tagged('post_install', '-at_install')
class TestPkChatSync(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_chat_people(cls)

    def setUp(self):
        super().setUp()
        self.specs = []
        enter(self, pk_chat_shell(self.env, managed=lambda kit: self.specs))
        self.kit = self.env['portal.kit']

    def _channel(self, key):
        return self.env['discuss.channel'].with_context(active_test=False).search([('pk_managed_key', '=', key)])

    def _roles(self, channel):
        return {m.partner_id.id: m.pk_role for m in channel.channel_member_ids}

    def _messages(self, channel):
        return self.env['mail.message'].search([('model', '=', 'discuss.channel'), ('res_id', '=', channel.id)])

    # UC-S1, UC-S2
    def test_create_add_remove_roles_rename(self):
        dana, avery, blake = self.dana.partner_id, self.avery.partner_id, self.blake.partner_id
        self.specs = [{'key': 'team-a', 'name': 'Team A parents', 'members': {dana.id: 'poster', avery.id: 'reader'}}]
        self.kit._pk_chat_sync()
        channel = self._channel('team-a')
        self.assertEqual((channel.channel_type, channel.name), ('group', 'Team A parents'))
        self.assertFalse(channel.group_public_id)
        self.assertEqual(self._roles(channel), {dana.id: 'poster', avery.id: 'reader'})
        self.specs = [{'key': 'team-a', 'name': 'Team A families', 'members': {dana.id: 'poster', avery.id: 'poster',
                                                                              blake.id: 'reader'}}]
        self.kit._pk_chat_sync()
        self.assertEqual(channel.name, 'Team A families')
        self.assertEqual(self._roles(channel), {dana.id: 'poster', avery.id: 'poster', blake.id: 'reader'})
        self.specs = [{'key': 'team-a', 'name': 'Team A families', 'members': {dana.id: 'poster'}}]
        self.kit._pk_chat_sync()
        self.assertEqual(self._roles(channel), {dana.id: 'poster'})
        self.assertFalse(self._messages(channel), 'no joined / invited / left message')

    # UC-S3
    def test_removed_key_archives(self):
        self.specs = [{'key': 'team-b', 'name': 'Team B', 'members': {self.avery.partner_id.id: 'reader'}}]
        self.kit._pk_chat_sync()
        channel = self._channel('team-b')
        self.specs = []
        self.kit._pk_chat_sync()
        self.assertTrue(channel.exists())
        self.assertFalse(channel.active)
        self.specs = [{'key': 'team-b', 'name': 'Team B', 'members': {self.avery.partner_id.id: 'reader'}}]
        self.kit._pk_chat_sync()
        self.assertTrue(channel.active)

    # UC-S4
    def test_idempotent(self):
        self.specs = [{'key': 'team-c', 'name': 'Team C', 'members': {self.dana.partner_id.id: 'poster',
                                                                     self.avery.partner_id.id: 'reader'}}]
        self.kit._pk_chat_sync()
        channel = self._channel('team-c')
        members = channel.channel_member_ids
        self.kit._pk_chat_sync()
        self.assertEqual(self._channel('team-c'), channel)
        self.assertEqual(channel.channel_member_ids, members)
        self.assertFalse(self._messages(channel))

    # UC-S5
    def test_new_member_history_read_and_not_mailed(self):
        dana = self.dana.partner_id
        self.specs = [{'key': 'team-d', 'name': 'Team D', 'members': {dana.id: 'poster'}}]
        self.kit._pk_chat_sync()
        channel = self._channel('team-d')
        message = channel.with_user(self.dana).message_post(body='Practice moved', message_type='comment',
                                                            subtype_xmlid='mail.mt_comment')
        self.specs[0]['members'][self.avery.partner_id.id] = 'reader'
        self.kit._pk_chat_sync()
        member = channel.channel_member_ids.filtered(lambda m: m.partner_id == self.avery.partner_id)
        self.assertEqual(member.pk_emailed_message_id, message)
        self.assertEqual(member.message_unread_counter, 0)

    # UC-S6
    def test_one_key(self):
        self.specs = [{'key': 'team-e', 'name': 'Team E', 'members': {}},
                      {'key': 'team-f', 'name': 'Team F', 'members': {}}]
        self.kit._pk_chat_sync(key='team-e')
        self.assertTrue(self._channel('team-e'))
        self.assertFalse(self._channel('team-f'))
