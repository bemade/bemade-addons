# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: starting a direct chat.

Acceptance criteria:

* UC-C1 ``POST /my/app/chat/start`` with a contact (``_pk_chat_contacts``)
  answers the chat's id: a ``chat`` channel of the two people; a second
  start (either way round) answers the same channel (one per pair).
* UC-C2 A partner who is not a contact answers 403 and creates nothing.
* UC-C3 ``GET /my/app/chat/contacts?q=`` lists the contacts (name only),
  filtered by the typed words.
* UC-C4 A share user cannot create a chat through Discuss
  (``/mail/action`` ``/discuss/get_or_create_chat``, the model method);
  an internal user still can (vanilla).
* UC-C5 The routes answer 404 while the chat is off.
Synthetic users only.
"""
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tests.common import pk_csrf, pk_frontend_langs

from .common import enter, pk_chat_people, pk_chat_shell


def only_blake_and_dana(kit, user):
    people = kit.env['res.partner'].sudo().search([('user_ids.login', 'in', ('pkc_blake', 'pkc_dana', 'pkc_avery'))])
    return people - user.partner_id


@tagged('post_install', '-at_install')
class TestPkChatContacts(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        pk_chat_people(cls)

    def setUp(self):
        super().setUp()
        enter(self, pk_chat_shell(self.env, contacts=only_blake_and_dana))

    def _start(self, login, partner):
        self.authenticate(login, login)
        return self.url_open('/my/app/chat/start', data={'csrf_token': pk_csrf(self), 'partner_id': partner.id})

    # UC-C1
    def test_start_one_chat_per_pair(self):
        response = self._start('pkc_avery', self.blake.partner_id)
        self.assertEqual(response.status_code, 200)
        channel = self.env['discuss.channel'].browse(response.json()['id'])
        self.assertEqual(channel.channel_type, 'chat')
        self.assertEqual(channel.channel_member_ids.partner_id, self.avery.partner_id | self.blake.partner_id)
        again = self._start('pkc_avery', self.blake.partner_id)
        self.assertEqual(again.json()['id'], channel.id)
        other_way = self._start('pkc_blake', self.avery.partner_id)
        self.assertEqual(other_way.json()['id'], channel.id)
        with_staff = self._start('pkc_avery', self.dana.partner_id)
        self.assertNotEqual(with_staff.json()['id'], channel.id)

    def test_own_last_message_preview_says_you(self):
        channel = self.env['discuss.channel'].browse(self._start('pkc_avery', self.blake.partner_id).json()['id'])
        channel.with_user(self.avery).message_post(
            body='See you at practice', message_type='comment', subtype_xmlid='mail.mt_comment')
        kit = self.env['portal.kit']
        [mine] = [r for r in kit.pk_chat_conversation_rows(self.avery) if r['id'] == channel.id]
        self.assertEqual(mine['preview'], 'You: See you at practice')
        [theirs] = [r for r in kit.pk_chat_conversation_rows(self.blake) if r['id'] == channel.id]
        self.assertEqual(theirs['preview'], 'See you at practice')

    # UC-C2
    @mute_logger('odoo.http')
    def test_non_contact_refused(self):
        before = self.env['discuss.channel'].search_count([])
        response = self._start('pkc_avery', self.casey.partner_id)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.env['discuss.channel'].search_count([]), before)

    # UC-C3
    def test_contacts_listed(self):
        self.authenticate('pkc_avery', 'pkc_avery')
        rows = self.url_open('/my/app/chat/contacts').json()['contacts']
        self.assertEqual([r['name'] for r in rows], ['Blake Testperson', 'Dana Staffperson'])
        self.assertEqual(set(rows[0]), {'id', 'name'})
        rows = self.url_open('/my/app/chat/contacts?q=dan').json()['contacts']
        self.assertEqual([r['name'] for r in rows], ['Dana Staffperson'])

    # UC-C4
    @mute_logger('odoo.http')
    def test_discuss_get_or_create_chat_refused_for_share(self):
        with self.assertRaises(AccessError):
            self.env['discuss.channel'].with_user(self.avery)._get_or_create_chat([self.blake.partner_id.id])
        self.authenticate('pkc_avery', 'pkc_avery')
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request('/mail/action', {
                'fetch_params': [['/discuss/get_or_create_chat', {'partners_to': [self.blake.partner_id.id]}]]})
        self.assertFalse(self.env['discuss.channel'].search([
            ('channel_type', '=', 'chat'), ('channel_member_ids.partner_id', '=', self.avery.partner_id.id)]))
        chat = self.env['discuss.channel'].with_user(self.dana)._get_or_create_chat([self.avery.partner_id.id])
        self.assertEqual(chat.channel_type, 'chat')

    # UC-C5
    @mute_logger('odoo.http')
    def test_off_is_404(self):
        enter(self, pk_chat_shell(self.env, contacts=only_blake_and_dana, chat=False))
        self.authenticate('pkc_avery', 'pkc_avery')
        for url in ('/my/app/chat/contacts', '/my/app/chat/conversations', '/my/app/chat/unread',
                    '/my/app/conversations'):
            self.assertEqual(self.url_open(url).status_code, 404, url)
