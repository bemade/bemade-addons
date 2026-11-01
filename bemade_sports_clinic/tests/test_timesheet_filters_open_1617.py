"""Task 1617 — the timesheets filters panel is open on every visit.
Synthetic fixtures only.

Acceptance criteria:

* AC-1 ``/my/sc/timesheets`` renders the filter disclosure
  (``form[data-sc-section="timesheets.filters"] details.o_sc_disclosure``)
  OPEN on every visit — with no filter, with filters, with a chosen sort —
  and it stays a disclosure (``<summary>`` toggle), so it can be collapsed.
* AC-2 Nothing else moves: the form still applies on change
  (``data-sc-autosubmit``), carries no sort select (the sort stays in the
  list header, #1607), keeps its « Group by » group, and the list header
  follows the form.
* AC-3 No remembered state: collapsing lasts for that visit only — the
  next visit renders the panel open again (browser: see
  test_timesheet_filters_open_tours_1617).
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestTimesheetFiltersOpen1617(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    @staticmethod
    def _form(tree):
        forms = tree.xpath('//form[@data-sc-section="timesheets.filters"]')
        return forms[0] if forms else None

    # -- AC-1 ------------------------------------------------------------
    def test_panel_open_on_every_visit(self):
        self._login_tp()
        for url in ('/my/sc/timesheets',
                    '/my/sc/timesheets?sortby=state',
                    '/my/sc/timesheets?team_id=%s' % self.team_a.id,
                    '/my/sc/timesheets?search=Synthetic&group_by=team'):
            _text, tree = self._get(url)
            form = self._form(tree)
            self.assertIsNotNone(form, url)
            details = form.xpath('./details[contains(concat(" ", @class, " "), " o_sc_disclosure ")]')
            self.assertEqual(len(details), 1, url)
            self.assertEqual(details[0].get('open'), 'open', url)
            # Still collapsible: a summary toggle first.
            self.assertEqual(details[0][0].tag, 'summary', url)

    # -- AC-2 ------------------------------------------------------------
    def test_rest_of_the_panel_unchanged(self):
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets')
        form = self._form(tree)
        self.assertEqual(form.get('data-sc-autosubmit'), '1')
        self.assertFalse(form.xpath('.//select[@name="sortby"]'))
        self.assertEqual(form.xpath('.//fieldset[@data-sc-section="timesheets.group"]//select/@name'), ['group_by'])
        header = tree.xpath('//*[@data-sc-section="timesheets.header"]')
        self.assertTrue(header)
        self.assertTrue(header[0].xpath('.//*[@data-sc-section="timesheets.sort"]'))
