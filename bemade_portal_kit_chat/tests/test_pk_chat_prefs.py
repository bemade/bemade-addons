# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the chat's notification kinds in « Settings ».

Acceptance criteria:

* UC-P1 With the chat on for the app, the settings section lists
  « Direct messages », « Group announcements » and « Replies in groups »,
  each with « Each message », « Daily digest », « Never ».
* UC-P2 With the chat off (no app turns it on: Fit Crew, any consumer
  without chat), the kinds do not apply and the section is hidden.
* UC-P3 Defaults: a portal user gets each / digest / digest, an internal
  user off for every kind.
Synthetic users only.
"""
from lxml import html as lxml_html

from odoo.tests import HttpCase, tagged

from odoo.addons.bemade_portal_kit.tests.common import pk_frontend_langs

from .common import enter, pk_chat_people, pk_chat_shell

KINDS = ['chat.direct', 'chat.announcement', 'chat.reply']


@tagged('post_install', '-at_install')
class TestPkChatPrefs(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)
        pk_chat_people(cls)

    def _settings(self):
        self.authenticate('pkc_avery', 'pkc_avery')
        return lxml_html.document_fromstring(self.url_open('/my/app/settings').text)

    # UC-P1
    def test_section_lists_chat_kinds(self):
        enter(self, pk_chat_shell(self.env))
        tree = self._settings()
        forms = tree.xpath('//section[@id="pk_notifications"]//form[@data-pk-notify-pref]')
        self.assertEqual([f.get('data-pk-notify-pref') for f in forms], KINDS)
        text = tree.xpath('//section[@id="pk_notifications"]')[0].text_content()
        for label in ('Direct messages', 'Group announcements', 'Replies in groups',
                      'Each message', 'Daily digest', 'Never'):
            self.assertIn(label, text)

    # UC-P2
    def test_section_hidden_without_chat(self):
        enter(self, pk_chat_shell(self.env, chat=False))
        self.assertEqual(self.env['portal.kit'].pk_notification_kinds(), [])
        self.assertFalse(self._settings().xpath('//section[@id="pk_notifications"]'))

    # UC-P3
    def test_defaults(self):
        enter(self, pk_chat_shell(self.env))
        self.assertEqual([self.avery._pk_notification_mode(k) for k in KINDS], ['each', 'digest', 'digest'])
        self.assertEqual([self.dana._pk_notification_mode(k) for k in KINDS], ['off', 'off', 'off'])
