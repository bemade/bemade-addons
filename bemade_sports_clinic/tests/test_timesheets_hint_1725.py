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

    # -- AC-1 ------------------------------------------------------------
    def test_hint_with_rows(self):
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets')
        self.assertTrue(tree.xpath('//*[@data-sc-section="timesheets.list"]'))
        hint = self._hint(tree)
        self.assertIn('o_sc_muted', hint.get('class'))
        self.assertIn('To add a timesheet, open the event concerned.', self._text(hint))
        self.assertEqual(hint.xpath('.//a/@href'), ['/my/events'])
        self.assertEqual(self._text(hint.xpath('.//a')[0]), 'Events')
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
        self.assertIn("No timesheets. Add one from the event's page.", self._text(empty[0]))
        self.assertEqual(empty[0].xpath('.//a/@href'), ['/my/events'])

    # -- AC-3 ------------------------------------------------------------
    def test_french(self):
        self._french_site()
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets?search=NoSuchSyntheticEvent')
        hint = self._text(self._hint(tree))
        self.assertIn("Pour ajouter une feuille de temps, ouvrez l'événement concerné.", hint)
        self.assertIn('Événements', hint)
        empty = self._text(tree.xpath('//p[@data-sc-section="timesheets.empty"]')[0])
        self.assertIn("Aucune feuille de temps. Ajoutez-en une depuis la page de l'événement.", empty)
        self.assertIn('Événements', empty)
