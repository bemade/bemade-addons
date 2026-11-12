# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5369 (kit P3c1): the clinic's glyphs extend the kit's icon.

* UC-C1 The clinic vocabulary (teams, players, clinic, bookings, timesheet,
  injury, epipen) renders through ``bemade_portal_kit.pk_icon`` (the clinic
  inherits ``pk_icon_extra``), byte-identical to the clinic's ``sc_icon``
  before the move (golden strings, 19.0 @ 5917030f); so do the kit's 37
  glyphs and the fallback, with the clinic installed.
* UC-C2 The clinic ships the Feather Icons MIT notice for the glyphs it
  keeps.
"""
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit.tests.test_pk_icon import FALLBACK, GOLDEN, HEAD, TAIL, render_icon

CLINIC_GOLDEN = {
    'teams': '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path>',
    'players': '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle>',
    'clinic': '<path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>',
    'bookings': '<rect x="3" y="4" width="18" height="18" rx="2"></rect><path d="M16 2v4M8 2v4M3 10h18"></path>',
    'timesheet': '<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>',
    'injury': '<rect x="3" y="7" width="18" height="14" rx="2"></rect><path d="M8 7V4h8v3M12 11v6M9 14h6"></path>',
    'epipen': '<rect x="9" y="2" width="6" height="14" rx="2"></rect><path d="M12 16v6M9 6h6M10 19h4"></path>',
}


@tagged('post_install', '-at_install')
class TestScIconExtra5369(TransactionCase):

    def test_clinic_glyphs_byte_identical(self):
        for name, inner in CLINIC_GOLDEN.items():
            with self.subTest(icon=name):
                self.assertEqual(render_icon(self.env, name), HEAD + inner + TAIL)

    def test_kit_glyphs_and_fallback_with_the_clinic(self):
        self.assertEqual(len(GOLDEN) + len(CLINIC_GOLDEN), 44)
        for name, inner in GOLDEN.items():
            with self.subTest(icon=name):
                self.assertEqual(render_icon(self.env, name), HEAD + inner + TAIL)
        for icon in ('no-such-icon', '', None):
            self.assertEqual(render_icon(self.env, icon), HEAD + FALLBACK + TAIL)

    def test_feather_notice(self):
        path = get_module_path('bemade_sports_clinic') + '/static/src/icons/LICENSE-feather.txt'
        with open(path, encoding='utf-8') as f:
            text = f.read()
        self.assertIn('Cole Bemis', text)
        self.assertIn('MIT', text)
