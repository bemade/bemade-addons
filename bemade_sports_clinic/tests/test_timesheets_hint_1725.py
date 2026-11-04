"""Task 1725 — Feuilles de temps: a hint says timesheets are added from
their event. Synthetic fixtures only.

Acceptance criteria:

* AC-1 ``/my/sc/timesheets`` shows, under the list header, an
  always-visible muted hint « To add a timesheet, open the event
  concerned. » with an « Events » link to ``/my/events`` — with rows and
  without.
* AC-2 With no timesheet (or none matching the filters) the empty state
  reads « No timesheets. Add one from the event's page. » with the same
  « Events » link (the event page's own « No timesheets yet. » is
  unchanged).
* AC-3 French (website-aware): « Pour ajouter une feuille de temps, ouvrez
  l'événement concerné. » / « Aucune feuille de temps. Ajoutez-en une
  depuis la page de l'événement. » and the link reads « Événements ».
  Review round 2 (owner 2026-10-27): « … ouvrez l'événement concerné :
  Mes événements sans feuilles de temps » (the link), same in the empty
  line.
* AC-4 (review round 1, 2026-10-27) Both « Events » links are app links
  (``o_sc_hint_link``: accent colour, weight 600) opening MY events with
  missing timesheets — the events page's « Missing timesheets » segment
  (``view_type=missing_timesheets``, the viewer as ``assigned_user_id``,
  ``no_default_dates=1``) — and that page shows the segment active.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestTimesheetsHint1725(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    @staticmethod
    def _text(node):
        return ' '.join(node.text_content().split())

    def _hint(self, tree):
        hints = tree.xpath('//p[@data-sc-section="timesheets.hint"]')
        self.assertEqual(len(hints), 1)
        return hints[0]

    def _french_site(self):
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
                website.default_lang_id = fr_lang
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        self.tp.write({'lang': 'fr_CA'})

    def _missing_url(self):
        return ('/my/events?view_type=missing_timesheets&assigned_user_id=%s&no_default_dates=1'
                % self.tp.id)

    def _assert_missing_link(self, node):
        links = node.xpath('.//a')
        self.assertEqual(len(links), 1)
        # website may prefix the language (/fr/…) on CI.
        self.assertTrue(links[0].get('href').endswith(self._missing_url()), links[0].get('href'))
        self.assertIn('o_sc_hint_link', links[0].get('class'))

    # -- AC-4 ------------------------------------------------------------
    def test_link_opens_missing_timesheets(self):
        self._login_tp()
        _text, tree = self._get(self._missing_url())
        chip = tree.xpath('//a[@data-sc-view="missing_timesheets"]')
        self.assertEqual(len(chip), 1)
        self.assertEqual(chip[0].get('aria-pressed'), 'true')

    # -- AC-1 ------------------------------------------------------------
    def test_hint_with_rows(self):
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets')
        self.assertTrue(tree.xpath('//*[@data-sc-section="timesheets.list"]'))
        hint = self._hint(tree)
        self.assertIn('o_sc_muted', hint.get('class'))
        self.assertIn('To add a timesheet, open the event concerned:', self._text(hint))
        self._assert_missing_link(hint)
        self.assertEqual(self._text(hint.xpath('.//a')[0]), 'My events without timesheets')
        # Under the list header, before the list.
        header = tree.xpath('//*[@data-sc-section="timesheets.header"]')[0]
        self.assertIs(header.getnext(), hint)
        self.assertFalse(tree.xpath('//*[@data-sc-section="timesheets.empty"]'))

    # -- AC-2 ------------------------------------------------------------
    def test_empty_state_points_to_events(self):
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets?search=NoSuchSyntheticEvent')
        self.assertFalse(tree.xpath('//*[@data-sc-section="timesheets.list"]'))
        self._hint(tree)
        empty = tree.xpath('//p[@data-sc-section="timesheets.empty"]')
        self.assertEqual(len(empty), 1)
        self.assertIn("No timesheets. Add one from the event's page:", self._text(empty[0]))
        self.assertEqual(self._text(empty[0].xpath('.//a')[0]), 'My events without timesheets')
        self._assert_missing_link(empty[0])

    # -- AC-3 ------------------------------------------------------------
    def test_french(self):
        self._french_site()
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets?search=NoSuchSyntheticEvent')
        hint = self._text(self._hint(tree))
        # Review round 2 (owner 2026-10-27): the link says where it goes.
        self.assertIn("Pour ajouter une feuille de temps, ouvrez l'événement concerné : "
                      "Mes événements sans feuilles de temps", hint)
        empty = self._text(tree.xpath('//p[@data-sc-section="timesheets.empty"]')[0])
        self.assertIn("Aucune feuille de temps. Ajoutez-en une depuis la page de l'événement : "
                      "Mes événements sans feuilles de temps", empty)
