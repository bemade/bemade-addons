# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5202 (kit P7): the hoot unit tests of the configure sheet's and the
anchoring's scripts (static/tests/*.test.js), headless."""
from odoo.tests import HttpCase, no_retry, tagged

from odoo.addons.bemade_portal_kit.tests.test_pk_hoot import hoot_hash, unit_test_error_checker

DASH_SUITE = '@bemade_portal_kit_dashboard'


@tagged('post_install', '-at_install')
class TestPkDashboardHoot(HttpCase):

    @no_retry
    def test_pk_dashboard_hoot_suite(self):
        url = ('/web/tests?headless&loglevel=2&preset=desktop&timeout=15000'
               f'&id={hoot_hash(DASH_SUITE)}')
        self.browser_js(url, '', '', login='admin', timeout=600,
                        success_signal='[HOOT] Test suite succeeded',
                        error_checker=unit_test_error_checker)
