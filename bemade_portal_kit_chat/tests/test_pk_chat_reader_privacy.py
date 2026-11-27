# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5520: a READER of a managed group never learns who the other
members are: not through the kit, Odoo's Discuss routes, the ORM (call_kw)
or the websocket. Posters and internal users: vanilla.

Fixtures: one managed group with 2 posters (Dana, internal; Emery, portal)
and 3 readers (Avery = A, Blake = B, Casey = C, portal), plus a non-managed
group and a direct chat as controls.

Acceptance criteria:

* UC-RP1 Kit: A sees the posters' names, their own, and « A member » with a
  neutral avatar for B's reply (thread, quoted parent, the post route's
  answer, each e-mail, digest, phone title and icon); the avatar route
  refuses B to A; a poster and an internal user see every real name; the
  alias comes from ``_pk_chat_reader_alias`` (« Un membre » in French).
* UC-RP2 Discuss routes as A on the group: members, messages,
  thread/messages, pinned, attachments, typing, mark_as_read, separator,
  join, sub-channel fetch / create and message/post are refused (404);
  ``/mail/data`` (init_messaging, channels_as_member, explicit ids,
  mail.thread) carries no member, count, uuid or persona of the group.
* UC-RP3 ORM as A (``with_user`` and call_kw): members only A's own row;
  the channel unreadable (members, partners, count); B's message
  unreadable; ``execute_command_who`` / ``_help`` refused; mention
  suggestions and partners by channel give no other reader; the rules are
  per user (no cache leak between users).
* UC-RP4 Mentions: A's reply with ``partner_ids`` / ``@everyone`` keeps no
  recipient (the membership oracle), ``sudo()`` included.
* UC-RP5 The store built for A (a backstop to the rules): no member, count,
  invitation, call or uuid of the group, no persona on its messages; a
  poster's and an internal user's store keep them.
* UC-RP6 Bus: A subscribes to ``(group, "pk_reader")``, never to the group
  (even when asked); every broadcast of the group (reply, reaction, typing,
  seen, edit, a member added / removed and the count, a call and its
  invitation) reaches ``(group, "pk_reader")`` only as a content-free
  ``pk_chat.ping`` for a new message, and A's own targets carry no other
  member; the group itself still gets the full payloads (posters, staff).
* UC-RP7 Controls: an internal user and a portal poster keep Discuss's
  members, typing, seen and personas; a non-managed group and a direct chat
  are unchanged for A (routes, store, bus).
Synthetic users only.
"""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tests.common import JsonRpcException
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tests.common import pk_csrf, pk_frontend_langs
from odoo.addons.http_routing.tests.common import MockRequest
from odoo.addons.mail.tools.discuss import Store

from ..models.bus_bus import PK_CHAT_PING, PK_READER_SUBCHANNEL
from ..models.discuss_channel import PK_CHAT_NEUTRAL_AVATAR
from .common import enter, everyone, pk_chat_people, pk_chat_shell

ALIAS = 'A member'
KEYS = '{"p256dh": "BFakeP256dh", "auth": "FakeAuth"}'


def _walk(value):
    """Every dict nested in ``value`` (a JSON-like structure)."""
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk(item)


def _partner_ids(value):
    """The ids of every ``res.partner`` record of the stores in ``value``."""
    ids = set()
    for node in _walk(value):
        for record in node.get('res.partner') or []:
            if isinstance(record, dict) and 'id' in record:
                ids.add(record['id'])
    return ids


class PkReaderCase(HttpCase):
    """The managed group of 2 posters and 3 readers, the controls, and the
    leak checks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        pk_chat_people(cls)
        cls.emery = new_test_user(cls.env, login='pkc_emery', name='Emery Testposter', groups='base.group_portal',
                                  lang='en_US', email='pkc_emery@example.com', tz='America/Toronto')
        cls.gale = new_test_user(cls.env, login='pkc_gale', name='Gale Testnewcomer', groups='base.group_portal',
                                 lang='en_US', email='pkc_gale@example.com', tz='America/Toronto')

    def setUp(self):
        super().setUp()
        self.members = {
            self.dana.partner_id.id: 'poster', self.emery.partner_id.id: 'poster',
            self.avery.partner_id.id: 'reader', self.blake.partner_id.id: 'reader',
            self.casey.partner_id.id: 'reader',
        }
        self.specs = [{'key': 'rp-1', 'name': 'Team Privacy parents', 'members': self.members}]
        enter(self, pk_chat_shell(self.env, managed=lambda kit: self.specs, contacts=everyone))
        self.kit = self.env['portal.kit']
        self.kit._pk_chat_sync()
        self.group = self.env['discuss.channel'].search([('pk_managed_key', '=', 'rp-1')])
        self.news = self._post(self.group, self.dana, 'Practice moved to 6 pm')
        self.b_reply = self._post(self.group, self.blake, 'Will bring water', parent_id=self.news.id)
        self.control = self.env['discuss.channel'].with_user(self.dana)._create_group(
            [self.avery.partner_id.id, self.blake.partner_id.id], name='Open carpool')
        self._post(self.control, self.blake, 'Carpool at 4')
        self.dm = self.kit.with_user(self.avery).pk_chat_start(self.dana.partner_id.id)
        self._post(self.dm, self.dana, 'Hello Avery')
        self.others = (self.blake | self.casey).partner_id  # what A must never learn

    # helpers ------------------------------------------------------------
    def _post(self, channel, user, body, **kw):
        # The kit's post path: sudo, the uid kept.
        return channel.with_user(user).sudo().message_post(
            body=body, message_type='comment', subtype_xmlid='mail.mt_comment', **kw)

    def _member(self, channel, user):
        return channel.sudo().channel_member_ids.filtered(lambda m: m.partner_id == user.partner_id)

    def _get(self, url):
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200, url)
        return response.json()

    def assertNoOthers(self, value, msg=None, others=None):
        """``value`` (JSON-like or text) names no other reader, carries none
        of their partner ids as store records, nor their avatar tokens."""
        others = self.others if others is None else others
        blob = value if isinstance(value, str) else json.dumps(value, default=str)
        for partner in others:
            self.assertNotIn(partner.name, blob, msg)
            self.assertNotIn(partner.name.split()[0], blob, msg)
            self.assertNotIn('/avatar/%s"' % partner.id, blob, msg)
        if not isinstance(value, str):
            self.assertFalse(_partner_ids(value) & set(others.ids), msg)

    def _rpc(self, url, params):
        return self.make_jsonrpc_request(url, params)

    def _call_kw(self, model, method, args, kwargs=None):
        return self._rpc('/web/dataset/call_kw/%s/%s' % (model, method), {
            'model': model, 'method': method, 'args': args, 'kwargs': kwargs or {}})


@tagged('post_install', '-at_install')
class TestPkChatReaderKit(PkReaderCase):

    # UC-RP1
    def test_reader_thread_alias(self):
        own = self._post(self.group, self.avery, 'Answering that', parent_id=self.b_reply.id)
        self._post(self.group, self.emery, 'Emery: bring a ball')
        self.authenticate('pkc_avery', 'pkc_avery')
        data = self._get('/my/app/chat/%s/messages' % self.group.id)
        rows = {m['id']: m for m in data['messages']}
        self.assertEqual(rows[self.news.id]['author_name'], 'Dana Staffperson')
        self.assertIn('/avatar/%s' % self.dana.partner_id.id, rows[self.news.id]['author_avatar_url'])
        self.assertEqual(rows[self.b_reply.id]['author_name'], ALIAS)
        self.assertEqual(rows[self.b_reply.id]['author_avatar_url'], PK_CHAT_NEUTRAL_AVATAR)
        self.assertEqual(rows[own.id]['author_name'], 'Avery Testperson')
        self.assertTrue(rows[own.id]['own'])
        self.assertEqual(rows[own.id]['parent']['author_name'], ALIAS, 'the quoted parent too')
        self.assertIn('Emery Testposter', [m['author_name'] for m in data['messages']])
        self.assertNoOthers(data)
        self.assertNoOthers(self._get('/my/app/chat/conversations'))

    def test_post_route_answers_with_the_alias(self):
        self.authenticate('pkc_avery', 'pkc_avery')
        response = self.url_open('/my/app/chat/%s/post' % self.group.id, data={
            'csrf_token': pk_csrf(self), 'body': 'Thanks Blake', 'parent_id': self.b_reply.id})
        self.assertEqual(response.status_code, 200)
        row = response.json()['message']
        self.assertEqual(row['author_name'], 'Avery Testperson')
        self.assertEqual(row['parent']['author_name'], ALIAS)

    def test_poster_and_internal_see_names(self):
        for login in ('pkc_emery', 'pkc_dana'):
            self.authenticate(login, login)
            data = self._get('/my/app/chat/%s/messages' % self.group.id)
            authors = [m['author_name'] for m in data['messages']]
            self.assertIn('Blake Testperson', authors, login)
            self.assertIn('Casey Testperson', [m['name'] for m in data['members']], login)

    @mute_logger('odoo.http')
    def test_avatar_route(self):
        self._post(self.group, self.avery, 'Mine', parent_id=self.news.id)
        self.authenticate('pkc_avery', 'pkc_avery')
        base = '/my/app/chat/%s/avatar/%%s' % self.group.id
        self.assertEqual(self.url_open(base % self.blake.partner_id.id).status_code, 404)
        self.assertEqual(self.url_open(base % self.casey.partner_id.id).status_code, 404)
        self.assertEqual(self.url_open(base % self.dana.partner_id.id).status_code, 200)
        self.assertEqual(self.url_open(base % self.avery.partner_id.id).status_code, 200)
        self.assertEqual(self.url_open(PK_CHAT_NEUTRAL_AVATAR).status_code, 200)
        self.authenticate('pkc_emery', 'pkc_emery')
        self.assertEqual(self.url_open(base % self.blake.partner_id.id).status_code, 200)

    def test_alias_hook(self):
        kit_cls = type(self.env['portal.kit'])
        with patch.object(kit_cls, '_pk_chat_reader_alias', lambda self, channel: 'A parent'):
            data = self.kit.with_user(self.avery).pk_chat_thread(self._member(self.group, self.avery))
        self.assertEqual([m['author_name'] for m in data['messages']], ['Dana Staffperson', 'A parent'])

    def test_alias_in_french(self):
        self.env['res.lang']._activate_lang('fr_CA')
        self.env['ir.module.module']._load_module_terms(['bemade_portal_kit_chat'], ['fr_CA'], overwrite=True)
        alias = self.kit.with_context(lang='fr_CA')._pk_chat_reader_alias(self.group)
        self.assertEqual(alias, 'Un membre')

    def _group_mails(self):
        return self.env['mail.mail'].search([('recipient_ids', 'in', self.avery.partner_id.ids),
                                             ('subject', 'like', 'Team Privacy parents')])

    def test_emails_each_and_digest(self):
        Pref = self.env['portal.kit.notification.pref']
        for kind in ('chat.announcement', 'chat.reply'):
            Pref.create({'user_id': self.avery.id, 'kind': kind, 'mode': 'each'})
        now = fields.Datetime.now()
        self._post(self.group, self.avery, 'Avery in the thread', parent_id=self.news.id)
        member = self._member(self.group, self.avery)
        member.pk_emailed_message_id = False
        self._post(self.group, self.casey, 'Also coming', parent_id=self.news.id)
        self.kit._pk_chat_cron_each(now=now + timedelta(minutes=11))
        mail = self._group_mails()
        self.assertEqual(len(mail), 1)
        self.assertIn('Also coming', mail.body_html)
        self.assertIn(ALIAS, mail.body_html)
        self.assertIn('Dana Staffperson', mail.body_html)
        self.assertNoOthers(mail.body_html)
        self.env['mail.mail'].search([('recipient_ids', 'in', self.avery.partner_id.ids)]).unlink()
        for pref in Pref.search([('user_id', '=', self.avery.id)]):
            pref.mode = 'digest'
        self.kit._pk_chat_cron_digest(now=now.replace(hour=23))
        mail = self.env['mail.mail'].search([('recipient_ids', 'in', self.avery.partner_id.ids),
                                             ('subject', '=', 'Your unread conversations')])
        self.assertEqual(len(mail), 1)
        self.assertIn('Team Privacy parents', mail.body_html)
        self.assertIn('%s: Also coming' % ALIAS, mail.body_html)
        self.assertNoOthers(mail.body_html, others=self.casey.partner_id)  # the open group names Blake, by design

    def test_push_title_alias(self):
        Device = self.env['mail.push.device'].sudo()
        Device.get_web_push_vapid_public_key()
        endpoints = {}
        for user in (self.avery, self.emery):
            endpoints[user] = 'https://push.example.com/send/%s' % user.login
            Device.create({'partner_id': user.partner_id.id, 'endpoint': endpoints[user], 'keys': KEYS})
            user._pk_notification_set_push(['chat.announcement', 'chat.reply'], True)
        sent = []

        def fake_send(channel, devices, private_key, public_key, payload_by_lang=None, payload=None):
            sent.append((devices.mapped('endpoint'), payload))

        enter(self, patch.object(type(self.env['discuss.channel']), '_web_push_send_notification', fake_send))
        self._post(self.group, self.avery, 'Avery in the thread', parent_id=self.news.id)
        sent.clear()
        self._post(self.group, self.blake, 'Also in the thread', parent_id=self.news.id)
        by_user = {user: [p for eps, p in sent if endpoints[user] in eps] for user in endpoints}
        self.assertEqual(len(by_user[self.avery]), 1)
        payload = by_user[self.avery][0]
        self.assertEqual(payload['title'], 'Team Privacy parents - %s' % ALIAS)
        self.assertEqual(payload['options']['icon'], PK_CHAT_NEUTRAL_AVATAR)
        self.assertNoOthers(payload)
        self.assertEqual(by_user[self.emery][0]['title'], 'Team Privacy parents - Blake Testperson')
        sent.clear()
        self._post(self.group, self.dana, 'Announcement')
        payload = [p for eps, p in sent if endpoints[self.avery] in eps][0]
        self.assertEqual(payload['title'], 'Team Privacy parents - Dana Staffperson')


@tagged('post_install', '-at_install')
class TestPkChatReaderCore(PkReaderCase):

    def _refused(self, url, params):
        with self.assertRaises(JsonRpcException, msg=url):
            self._rpc(url, params)

    # UC-RP2
    @mute_logger('odoo.http')
    def test_discuss_routes_refused(self):
        gid = self.group.id
        self.authenticate('pkc_avery', 'pkc_avery')
        self._refused('/discuss/channel/members', {'channel_id': gid, 'known_member_ids': []})
        self._refused('/discuss/channel/messages', {'channel_id': gid})
        self._refused('/mail/thread/messages', {'thread_model': 'discuss.channel', 'thread_id': gid})
        self._refused('/discuss/channel/pinned_messages', {'channel_id': gid})
        self._refused('/discuss/channel/attachments', {'channel_id': gid})
        self._refused('/discuss/channel/notify_typing', {'channel_id': gid, 'is_typing': True})
        self._refused('/discuss/channel/mark_as_read', {'channel_id': gid, 'last_message_id': self.b_reply.id})
        self._refused('/discuss/channel/set_new_message_separator', {'channel_id': gid, 'message_id': 1})
        self._refused('/discuss/channel/join', {'channel_id': gid})
        self._refused('/discuss/channel/sub_channel/fetch', {'parent_channel_id': gid})
        self._refused('/discuss/channel/sub_channel/create', {'parent_channel_id': gid})
        self._refused('/mail/message/post', {'thread_model': 'discuss.channel', 'thread_id': gid, 'post_data': {
            'body': 'Hi', 'message_type': 'comment', 'parent_id': self.news.id}})
        # The control group and the direct chat: unchanged.
        members = self._rpc('/discuss/channel/members', {'channel_id': self.control.id, 'known_member_ids': []})
        self.assertIn(self.blake.partner_id.id, _partner_ids(members))
        messages = self._rpc('/discuss/channel/messages', {'channel_id': self.dm.id})
        self.assertTrue(messages['messages'])

    def test_mail_data_hides_the_group(self):
        self.authenticate('pkc_avery', 'pkc_avery')
        data = self._rpc('/mail/data', {'fetch_params': [
            'init_messaging', 'channels_as_member', ['discuss.channel', [self.group.id]],
            ['mail.thread', {'thread_model': 'discuss.channel', 'thread_id': self.group.id,
                             'request_list': ['followers', 'attachments']}],
        ]})
        channels = {c['id']: c for c in data.get('discuss.channel', [])}
        group = channels.get(self.group.id, {})
        for key in ('member_count', 'uuid', 'channel_member_ids', 'channel_name_member_ids', 'invited_member_ids',
                    'rtc_session_ids'):
            self.assertNotIn(key, group)
        self.assertIn(self.control.id, channels, 'the control group is still listed')
        self.assertIn('member_count', channels[self.control.id])
        self.assertNoOthers({k: v for k, v in data.items() if k != 'discuss.channel'}
                            | {'group': group}, others=self.casey.partner_id)
        member_rows = [m for m in data.get('discuss.channel.member', [])
                       if (m.get('channel_id') or {}).get('id') == self.group.id]
        self.assertFalse([m for m in member_rows if m.get('partner_id') != self.avery.partner_id.id])
        blob = json.dumps(data)
        self.assertNotIn(self.group.uuid, blob)
        self.assertNotIn('Casey', blob)

    # UC-RP3
    @mute_logger('odoo.http', 'odoo.models', 'odoo.addons.base.models.ir_rule')
    def test_call_kw(self):
        gid = self.group.id
        self.authenticate('pkc_avery', 'pkc_avery')
        rows = self._call_kw('discuss.channel.member', 'search_read', [[['channel_id', '=', gid]], ['partner_id']])
        self.assertEqual([r['partner_id'][0] for r in rows], [self.avery.partner_id.id])
        for method, args in (
            ('read', [[gid], ['channel_partner_ids', 'member_count', 'channel_member_ids']]),
            ('execute_command_who', [[gid]]),
            ('execute_command_help', [[gid]]),
        ):
            with self.assertRaises(JsonRpcException, msg=method):
                self._call_kw('discuss.channel', method, args)
        self.assertFalse(self._call_kw('discuss.channel', 'search_read', [[['id', '=', gid]], ['member_count']]))
        with self.assertRaises(JsonRpcException):
            self._call_kw('mail.message', 'read', [[self.b_reply.id], ['author_id']])
        rows = self._call_kw('mail.message', 'search_read', [
            [['model', '=', 'discuss.channel'], ['res_id', '=', gid]], ['author_id']])
        self.assertNoOthers(rows)
        suggestions = self._call_kw('res.partner', 'get_mention_suggestions_from_channel', [gid, ''])
        self.assertNoOthers(suggestions)
        rows = self._call_kw('res.partner', 'search_read', [[['channel_ids', 'in', [gid]]], ['name']])
        self.assertNoOthers(rows)

    @mute_logger('odoo.models', 'odoo.addons.base.models.ir_rule')
    def test_orm_with_user(self):
        group = self.group.with_user(self.avery)
        Member = self.env['discuss.channel.member'].with_user(self.avery)
        self.assertEqual(Member.search([('channel_id', '=', self.group.id)]).partner_id, self.avery.partner_id)
        self.assertFalse(self.env['discuss.channel'].with_user(self.avery).search([('id', '=', self.group.id)]))
        with self.assertRaises(AccessError):
            group.read(['channel_partner_ids', 'member_count', 'channel_member_ids'])
        with self.assertRaises(AccessError):
            self.b_reply.with_user(self.avery).read(['author_id'])
        with self.assertRaises(AccessError):
            group.execute_command_who()
        with self.assertRaises(AccessError):
            group.execute_command_help()
        # A sub-thread of the group is hidden too.
        sub = self.group.with_user(self.dana)._create_sub_channel(from_message_id=self.news.id)
        self.assertFalse(self.env['discuss.channel'].with_user(self.avery).search([('id', '=', sub.id)]))
        # The reader's own message stays theirs.
        own = self._post(self.group, self.avery, 'Mine', parent_id=self.news.id)
        self.assertEqual(own.with_user(self.avery).read(['author_id'])[0]['author_id'][0], self.avery.partner_id.id)

    def test_rules_per_user(self):
        def members_seen(user):
            return self.env['discuss.channel.member'].with_user(user).search(
                [('channel_id', '=', self.group.id)]).partner_id

        self.assertEqual(members_seen(self.avery), self.avery.partner_id)
        self.assertEqual(len(members_seen(self.emery)), 5, 'a portal poster sees the members')
        self.assertEqual(len(members_seen(self.dana)), 5, 'an internal user sees the members')
        self.assertEqual(members_seen(self.blake), self.blake.partner_id)
        self.assertEqual(members_seen(self.avery), self.avery.partner_id)
        self.assertTrue(self.env['discuss.channel'].with_user(self.emery).search([('id', '=', self.group.id)]))
        self.assertFalse(self.env['discuss.channel'].with_user(self.casey).search([('id', '=', self.group.id)]))

    # UC-RP4
    def test_mention_oracle_closed(self):
        x = self.env['res.partner'].create({'name': 'Outsider Synthetic'})
        targets = [self.blake.partner_id.id, x.id]
        reply = self._post(self.group, self.avery, 'Hi', parent_id=self.news.id, partner_ids=targets)
        self.assertFalse(reply.partner_ids)
        reply = self._post(self.group, self.avery, 'Hi all', parent_id=self.news.id,
                           special_mentions=['everyone'])
        self.assertFalse(reply.partner_ids)
        with self.assertRaises(AccessError):
            self.group.with_user(self.avery).message_post(
                body='Hi', message_type='comment', parent_id=self.news.id, partner_ids=targets)
        # A poster's mention still works.
        news = self._post(self.group, self.emery, 'Hello Blake', partner_ids=[self.blake.partner_id.id])
        self.assertEqual(news.partner_ids, self.blake.partner_id)

    # UC-RP7
    def test_internal_and_poster_vanilla(self):
        for login in ('pkc_dana', 'pkc_emery'):
            self.authenticate(login, login)
            members = self._rpc('/discuss/channel/members', {'channel_id': self.group.id, 'known_member_ids': []})
            self.assertTrue(set(self.others.ids) <= _partner_ids(members), login)
            messages = self._rpc('/discuss/channel/messages', {'channel_id': self.group.id})
            self.assertIn(self.blake.partner_id.id, _partner_ids(messages), login)
            data = self._rpc('/mail/data', {'fetch_params': ['channels_as_member']})
            group = [c for c in data['discuss.channel'] if c['id'] == self.group.id][0]
            self.assertEqual(group['member_count'], 5, login)
            self.assertIn('uuid', group, login)


@tagged('post_install', '-at_install')
class TestPkChatReaderStoreBus(PkReaderCase):

    def _capture(self, action):
        """The bus rows ``action`` sends: ``[(target, type, payload)]``,
        ``target`` = ``('discuss.channel', id[, sub])``, ``('res.users', id)``..."""
        self.env.cr.precommit.run()
        Bus = self.env['bus.bus'].sudo()
        last = Bus.search([], order='id desc', limit=1).id or 0
        action()
        self.env.cr.precommit.run()
        rows = []
        for row in Bus.search([('id', '>', last)], order='id'):
            channel = json.loads(row.channel)
            message = json.loads(row.message)
            rows.append((tuple(channel[1:]) if isinstance(channel, list) else channel,
                         message['type'], message['payload']))
        return rows

    def _check_reader_rows(self, rows, label, pings=0):
        group = ('discuss.channel', self.group.id)
        reader = group + (PK_READER_SUBCHANNEL,)
        to_reader = [(t, p) for target, t, p in rows if target == reader]
        self.assertEqual(len(to_reader), pings, label)
        for notification_type, payload in to_reader:
            self.assertEqual(notification_type, PK_CHAT_PING, label)
            self.assertLessEqual(set(payload), {'channel_id', 'message_id'}, label)
            self.assertEqual(payload['channel_id'], self.group.id, label)
        mine = {('res.users', self.avery.id), ('res.partner', self.avery.partner_id.id)}
        self.assertNoOthers([p for target, t, p in rows if target in mine], label)
        return [(t, p) for target, t, p in rows if target == group]

    # UC-RP6
    def test_subscriptions(self):
        def channels(user, asked=()):
            env = self.env(user=user)
            with MockRequest(env) as request:
                request.session.uid = user.id
                return env['ir.websocket']._prepare_subscribe_data(list(asked), 0)['channels']

        asked = ['discuss.channel_%s' % self.group.id]
        mine = channels(self.avery, asked)
        self.assertNotIn(self.group, mine)
        self.assertIn((self.group, PK_READER_SUBCHANNEL), mine)
        self.assertIn(self.control, mine)
        self.assertIn(self.dm, mine)
        self.assertIn(self.avery.partner_id, mine)
        poster = channels(self.emery)
        self.assertIn(self.group, poster)
        self.assertNotIn((self.group, PK_READER_SUBCHANNEL), poster)
        staff = channels(self.dana)
        self.assertIn(self.group, staff)
        self.assertIn((self.group, 'internal_users'), staff)

    def test_new_message_ping_only(self):
        rows = self._capture(lambda: self._post(self.group, self.blake, 'Once more', parent_id=self.news.id))
        bare = self._check_reader_rows(rows, 'reply', pings=1)
        ping = [p for target, t, p in rows if target[-1] == PK_READER_SUBCHANNEL][0]
        self.assertTrue(ping['message_id'])
        full = [p for t, p in bare if t == 'discuss.channel/new_message']
        self.assertEqual(len(full), 1, 'posters and staff keep the full payload')
        self.assertIn(self.blake.partner_id.id, _partner_ids(full))

    def test_other_broadcasts_never_reach_the_reader(self):
        blake = self._member(self.group, self.blake)
        unseen = self._post(self.group, self.dana, 'Seen?')
        events = {
            'reaction': lambda: self.b_reply.with_user(self.dana).sudo()._message_reaction(
                '👍', 'add', self.dana.partner_id, self.env['mail.guest']),
            'typing': lambda: blake._notify_typing(True),
            'seen': lambda: blake._mark_as_read(unseen.id),
            'edit': lambda: self.group.with_user(self.dana)._message_update_content(self.news, body='Moved to 7 pm'),
            'call': lambda: self._member(self.group, self.dana).with_user(self.dana).sudo()._rtc_join_call(),
        }
        for label, action in events.items():
            rows = self._capture(action)
            # A call posts its « started a call » notice: a new message, so one ping.
            bare = self._check_reader_rows(rows, label, pings=1 if label == 'call' else 0)
            self.assertTrue(bare, '%s: the group still gets it' % label)

    def test_sync_members_and_count(self):
        def add_gale():
            self.members[self.gale.partner_id.id] = 'reader'
            self.kit._pk_chat_sync()

        rows = self._capture(add_gale)
        bare = self._check_reader_rows(rows, 'member added')
        self.assertTrue(any('member_count' in json.dumps(p) for t, p in bare), 'the count goes to the group')
        gale = {('res.users', self.gale.id), ('res.partner', self.gale.partner_id.id)}
        joined = [p for target, t, p in rows if target in gale]
        self.assertTrue(joined, 'the newcomer is told they joined')
        self.assertNoOthers(joined, 'the newcomer learns no member',
                            others=(self.avery | self.blake | self.casey).partner_id)

        def remove_casey():
            del self.members[self.casey.partner_id.id]
            self.kit._pk_chat_sync()

        rows = self._capture(remove_casey)
        self._check_reader_rows(rows, 'member removed')
        self.assertNotIn(self.casey.partner_id, self.group.sudo().channel_member_ids.partner_id)

    def test_unfollow(self):
        rows = self._capture(lambda: self.group.with_user(self.blake).sudo()._action_unfollow(
            self.blake.partner_id, post_leave_message=False))
        self.assertTrue(self._check_reader_rows(rows, 'unfollow'))

    # UC-RP5
    def test_store_for_a_reader(self):
        dana_member = self._member(self.group, self.dana)
        self._member(self.group, self.casey).sudo().rtc_inviting_session_id = False
        dana_member.with_user(self.dana).sudo()._rtc_join_call()
        group = self.group.sudo()

        def store(user):
            return Store(bus_channel=user).add(group).add(group._get_last_messages()).add(
                self.b_reply.sudo()).get_result()

        reader = store(self.avery)
        channel = [c for c in reader['discuss.channel'] if c['id'] == self.group.id][0]
        for key in ('member_count', 'uuid', 'channel_member_ids', 'channel_name_member_ids', 'invited_member_ids',
                    'rtc_session_ids', 'create_uid'):
            self.assertNotIn(key, channel)
        self.assertEqual(channel['name'], 'Team Privacy parents')
        message = [m for m in reader['mail.message'] if m['id'] == self.b_reply.id][0]
        self.assertNotIn('author_id', message)
        self.assertNoOthers(reader)
        for user in (self.emery, self.dana):
            full = store(user)
            channel = [c for c in full['discuss.channel'] if c['id'] == self.group.id][0]
            self.assertEqual(channel['member_count'], 5, user.login)
            self.assertIn('uuid', channel, user.login)
            message = [m for m in full['mail.message'] if m['id'] == self.b_reply.id][0]
            self.assertEqual(message['author_id'], self.blake.partner_id.id, user.login)

    # UC-RP7
    def test_controls_unchanged(self):
        rows = self._capture(lambda: self._post(self.control, self.blake, 'Carpool at 5'))
        self.assertFalse([r for r in rows if len(r[0]) == 3 and r[0][2] == PK_READER_SUBCHANNEL])
        self.assertTrue([r for r in rows if r[0] == ('discuss.channel', self.control.id)])
        rows = self._capture(lambda: self._post(self.dm, self.dana, 'See you'))
        self.assertTrue([r for r in rows if r[0] == ('discuss.channel', self.dm.id)])
        reader = Store(bus_channel=self.avery).add(self.control.sudo()).get_result()
        channel = [c for c in reader['discuss.channel'] if c['id'] == self.control.id][0]
        self.assertEqual(channel['member_count'], 3)
