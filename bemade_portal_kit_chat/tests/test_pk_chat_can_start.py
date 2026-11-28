# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5583: « New conversation » only for a user with someone to write to.

Acceptance criteria:

* UC-N1 ``GET /my/app/chat/conversations`` answers ``can_start: false``
  for a user without contacts (``_pk_chat_contacts``, default: nobody) and
  ``can_start: true`` for a user with at least one contact.
* UC-N2 The user's own partner is not a contact: a hook that returns only
  the user answers ``can_start: false``.
* UC-N3 The bubble's « New conversation » button is rendered hidden (the
  client shows it once the list says ``can_start``): no flash for a user
  without contacts.
Synthetic users only.
"""
from lxml import html

from odoo.tests import HttpCase, tagged

from odoo.addons.bemade_portal_kit.tests.common import pk_frontend_langs

from .common import enter, pk_chat_people, pk_chat_shell


def only_dana(kit, user):
    return kit.env['res.partner'].sudo().search([('user_ids.login', '=', 'pkc_dana')]) - user.partner_id


@tagged('post_install', '-at_install')
class TestPkChatCanStart(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        pk_chat_people(cls)

    def _can_start(self, login):
        self.authenticate(login, login)
        response = self.url_open('/my/app/chat/conversations')
        self.assertEqual(response.status_code, 200)
        return response.json()['can_start']

    # UC-N1
    def test_no_contacts_cannot_start(self):
        enter(self, pk_chat_shell(self.env))
        self.assertIs(self._can_start('pkc_avery'), False)

    def test_a_contact_can_start(self):
        enter(self, pk_chat_shell(self.env, contacts=only_dana))
        self.assertIs(self._can_start('pkc_avery'), True)

    # UC-N2
    def test_only_self_cannot_start(self):
        enter(self, pk_chat_shell(self.env, contacts=lambda kit, user: user.partner_id))
        self.assertIs(self._can_start('pkc_avery'), False)

    # UC-N3
    def test_button_rendered_hidden(self):
        enter(self, pk_chat_shell(self.env, contacts=only_dana))
        self.authenticate('pkc_avery', 'pkc_avery')
        response = self.url_open('/my/app/more')
        self.assertEqual(response.status_code, 200)
        [button] = html.fromstring(response.content).xpath('//button[@data-pk-chat-new]')
        self.assertIsNotNone(button.get('hidden'))
