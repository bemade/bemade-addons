# Part of bemade_sports_clinic. License LGPL-3.
"""Owner review 2026-10-21 (#1634): a player card whose player moved to
another dashboard section after a quick status change still gets a fresh
fragment (the same player's card from the other section, scope rewritten)."""
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.controllers.app_shell import sc_fill_moved_row_fragments


@tagged('post_install', '-at_install')
class TestMovedRowFragment1634(TransactionCase):

    def test_missing_scope_filled_from_other_scope(self):
        html = ('<div data-sc-fragment="sports.patient:7:row-dash">'
                '<button aria-controls="sc-pill-sports-patient-7-practice-dash">P</button>'
                '<span id="sc-pill-sports-patient-7-practice-dash"></span>'
                '<button aria-controls="sc-row-detail-dash-7">D</button></div>')
        found = {'sports.patient:7:row-dash': html}
        keys = ['sports.patient:7:row-dash', 'sports.patient:7:row-watch']
        sc_fill_moved_row_fragments(found, keys)
        filled = found['sports.patient:7:row-watch']
        self.assertIn('data-sc-fragment="sports.patient:7:row-watch"', filled)
        self.assertIn('sc-pill-sports-patient-7-practice-watch', filled)
        self.assertIn('sc-row-detail-watch-7', filled)
        self.assertNotIn('-dash', filled)
        # the original is untouched
        self.assertEqual(found['sports.patient:7:row-dash'], html)

    def test_other_players_and_absent_players_untouched(self):
        found = {'sports.patient:7:row-dash': '<div data-sc-fragment="sports.patient:7:row-dash"></div>'}
        keys = ['sports.patient:8:row-watch', 'sports.patient:7:status']
        sc_fill_moved_row_fragments(found, keys)
        self.assertEqual(set(found), {'sports.patient:7:row-dash'})
