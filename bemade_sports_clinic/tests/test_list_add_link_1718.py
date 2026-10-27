"""Task 1718 — the list headers' « + Ajouter » is a green-text link (the
« Historique » style), right-aligned. Synthetic fixtures only.

Acceptance criteria:

* AC-1 In ``sc_list_header`` the Add control — all three variants
  (``add_url`` link, ``add_sheet`` and ``add_panel`` buttons) — carries the
  green-text link classes (``o_sc_section_more o_sc_link_btn``), keeps the
  stable ``o_sc_list_add`` hook, the plus icon and « Add » (« Ajouter »), and
  is no longer a filled button (no ``o_sc_btn`` / ``o_sc_btn_primary``).
* AC-2 It is the LAST item of the header (right-aligned, after the count and
  the sort menu). Superseded by review round 1 (owner 2026-10-27): it is
  the FIRST item (just above the list's top-left edge, where the filled
  button sat) and carries no « + » icon — AC-1's « the plus icon » too.
* AC-3 The toggle/aria behaviour is unchanged (``aria-controls``,
  ``aria-expanded``, ``data-sc-list-add-toggle``; ``data-sc-sheet-open``).
* AC-4 Form submit buttons inside the panels stay filled.

The look (light/dark, 44 px target, the open state) stays UNVERIFIED until
/dev-review clicks it through.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_list_header_1607 import ListHeader1607Common


@tagged('post_install', '-at_install')
class TestListAddLink1718(ListHeader1607Common):

    def _all_adds(self, tree):
        return tree.xpath('//div[contains(concat(" ", @class, " "), " o_sc_list_header ")]'
                          '//*[contains(concat(" ", @class, " "), " o_sc_list_add ")]')

    def _check(self, add):
        classes = add.get('class').split()
        self.assertIn('o_sc_section_more', classes)
        self.assertIn('o_sc_link_btn', classes)
        self.assertNotIn('o_sc_btn', classes)
        self.assertNotIn('o_sc_btn_primary', classes)
        # Review round 1: no « + » icon, the FIRST item of its header.
        self.assertFalse(add.xpath('.//*[contains(@class, "o_sc_icon")]'))
        self.assertEqual(' '.join(add.text_content().split()), 'Add')
        self.assertIsNone(add.getprevious())

    def test_link_style_everywhere(self):
        self._login_tp()
        player = '/my/player?player_id=%s' % self.player.id
        seen = set()
        for url in ('/my/players', '/my/events',
                    '/my/team?team_id=%s&tab=players' % self.team_a.id,
                    player + '&tab=injuries', player + '&tab=info', player + '&tab=notes',
                    player + '&tab=activities', player + '&tab=documents'):
            _text, tree = self._get(url)
            adds = self._all_adds(tree)
            self.assertTrue(adds, url)
            for add in adds:
                self._check(add)
                if add.tag == 'a':
                    seen.add('url')
                elif add.get('data-sc-sheet-open'):
                    seen.add('sheet')
                elif add.get('data-sc-list-add-toggle'):
                    seen.add('panel')
                    self.assertTrue(add.get('aria-controls'))
                    self.assertIn(add.get('aria-expanded'), ('true', 'false'))
        self.assertEqual(seen, {'url', 'sheet', 'panel'})

    def test_panel_submits_stay_filled(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        submit = tree.xpath('//details[@id="sc_activity_add"]//button[@type="submit"]')[0]
        self.assertIn('o_sc_btn_primary', submit.get('class'))
