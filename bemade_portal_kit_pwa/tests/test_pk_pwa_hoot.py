# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5201 (kit P6): run this addon's hoot unit tests
(static/tests/*.test.js) headless, scoped to its own suite (the kit's
runner, ``bemade_portal_kit/tests/test_pk_hoot.py``)."""
from odoo.tests import HttpCase, no_retry, tagged

from odoo.addons.bemade_portal_kit.tests.test_pk_hoot import hoot_hash, unit_test_error_checker

PWA_SUITE = '@bemade_portal_kit_pwa'


@tagged('post_install', '-at_install')
class TestPkPwaHoot(HttpCase):

    @no_retry
    def test_pk_pwa_hoot_suite(self):
        url = ('/web/tests?headless&loglevel=2&preset=desktop&timeout=15000'
               f'&id={hoot_hash(PWA_SUITE)}')
        self.browser_js(url, '', '', login='admin', timeout=600,
                        success_signal='[HOOT] Test suite succeeded',
                        error_checker=unit_test_error_checker)
