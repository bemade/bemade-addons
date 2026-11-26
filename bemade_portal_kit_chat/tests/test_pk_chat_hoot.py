# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the hoot unit tests of the chat client (static/tests/*.test.js):
the window swap, the sessionStorage restore, the reader's composer, Enter
to send, the backend palette's portal partners. Headless, scoped to this
addon's suite (the kit's runner)."""
from odoo.tests import HttpCase, no_retry, tagged

from odoo.addons.bemade_portal_kit.tests.test_pk_hoot import hoot_hash, unit_test_error_checker

CHAT_SUITE = '@bemade_portal_kit_chat'


@tagged('post_install', '-at_install')
class TestPkChatHoot(HttpCase):

    @no_retry
    def test_pk_chat_hoot_suite(self):
        url = ('/web/tests?headless&loglevel=2&preset=desktop&timeout=15000'
               f'&id={hoot_hash(CHAT_SUITE)}')
        self.browser_js(url, '', '', login='admin', timeout=600,
                        success_signal='[HOOT] Test suite succeeded',
                        error_checker=unit_test_error_checker)
