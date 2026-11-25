# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5197 (P2): run the kit's hoot unit tests (static/tests/*.test.js)
headless, scoped to the kit's own suite.

Same runner as ``web``'s ``WebSuite.test_unit_desktop``, with the hoot
``id=`` filter set to the kit's job (« @bemade_portal_kit »): only the kit's
test files run, not every installed addon's. Synthetic fixtures only.
"""
from odoo.tests import HttpCase, no_retry, tagged

KIT_SUITE = '@bemade_portal_kit'


def hoot_hash(name):
    """``HOOTCommon._generate_hash`` (web/tests/test_js.py)."""
    value = 0
    for char in name:
        value = (value << 5) - value + ord(char)
        value = value & 0xFFFFFFFF
    return f'{value:08x}'


def unit_test_error_checker(message):
    return '[HOOT]' not in message


@tagged('post_install', '-at_install')
class TestPkHoot(HttpCase):

    def test_suite_hash(self):
        # The reference value of web's own test (test_generate_hoot_hash).
        self.assertEqual(hoot_hash('@web/core'), 'e39ce9ba')

    @no_retry
    def test_pk_hoot_suite(self):
        url = (
            '/web/tests?headless&loglevel=2&preset=desktop&timeout=15000'
            f'&id={hoot_hash(KIT_SUITE)}'
        )
        self.browser_js(
            url, '', '', login='admin', timeout=900,
            success_signal='[HOOT] Test suite succeeded',
            error_checker=unit_test_error_checker,
        )
