"""Task 1743 — phone: the players filters in ONE « Filters (N) » disclosure,
and the event page's staff / organization emails readable (never cut
mid-word). Synthetic fixtures only (this repository is public).

Acceptance criteria:

* UC-1 /my/players: the « First name » / « Last name » boxes and « Search »
  stay in sight; « Suivis ★ » (#1738), jersey, team, organization, match,
  practice and « Clear » are inside ONE disclosure (data-pk-section
  « players.filters »), closed without an active filter.
* UC-2 With filters set (« Suivis » counts) the disclosure is open and its
  summary reads « Filters (N) » (« Filtres (N) »).
* UC-3 The event page's emails carry a break opportunity before « @ »
  (<wbr>) and read as the address.
* UC-4 In a browser, phone 390 px: the filters folded take one line under
  « Search »; opening them shows the chip; on the event page the assigned
  person's email sits under the name, inside its column, at most at « @ »
  wrapped (static/tests/tours/sc_phone_filters_email_1743_tours.js).
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common

FILTERS = '//form[@data-pk-section="players.search"]/details[@data-pk-section="players.filters"]'


class _Common1743(Dashboard1624Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tp.partner_id.email = 'synthetic.therapist.longname@example.com'
        cls.event.partner_id = cls.env['res.partner'].create({
            'name': 'SC1743 Org', 'is_company': True,
            'email': 'info.synthetic-organization-name@example.com'})


@tagged('post_install', '-at_install')
class TestPhoneFiltersEmail1743(_Common1743):

    def _filters(self, url):
        _text, tree = self._get(url)
        found = tree.xpath(FILTERS)
        self.assertEqual(len(found), 1)
        return tree, found[0]

    def test_filters_folded(self):
        self._login_tp()
        tree, details = self._filters('/my/players')
        self.assertIsNone(details.get('open'))
        form = tree.xpath('//form[@data-pk-section="players.search"]')[0]
        # In sight: the name boxes and « Search ».
        for name in ('first_name', 'last_name'):
            box = form.xpath('.//input[@name="%s"]' % name)[0]
            self.assertFalse([a for a in box.iterancestors() if a.tag == 'details'], name)
        submit = form.xpath('.//button[@type="submit"]')
        self.assertEqual(len(submit), 1)
        self.assertFalse([a for a in submit[0].iterancestors() if a.tag == 'details'])
        # Folded: the chip, the other filters, « Clear ».
        self.assertTrue(details.xpath('.//a[@data-sc-action="players.followed"]'))
        for name in ('jersey_number', 'team_id', 'organization_id', 'match_status', 'practice_status'):
            self.assertTrue(details.xpath('.//*[@name="%s"]' % name), name)
        self.assertTrue(details.xpath('.//a[@data-pk-filter-reset]'))
        self.assertFalse(details.xpath('./summary//*[@data-sc-filter-count]'))
        self.assertEqual(len(form.xpath('.//details')), 1, 'ONE disclosure')

    def test_filters_open_with_count(self):
        self._login_tp()
        _tree, details = self._filters('/my/players?followed=1&team_id=%s' % self.team_a.id)
        self.assertEqual(details.get('open'), 'open')
        count = details.xpath('./summary//*[@data-sc-filter-count]')[0]
        self.assertEqual(count.text_content().strip(), '(2)')
        summary = ' '.join(details.xpath('./summary')[0].text_content().split())
        self.assertEqual(summary, 'Filters (2)')
        # A name search alone does not open it.
        _tree, details = self._filters('/my/players?last_name=Synth')
        self.assertIsNone(details.get('open'))

    def test_filters_french(self):
        self.env['res.lang']._activate_lang('fr_CA')
        self.env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if self.env['ir.module.module']._get('website').state == 'installed':
            fr_lang = self.env['res.lang']._lang_get('fr_CA')
            for website in self.env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        self.tp.write({'lang': 'fr_CA'})
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _tree, details = self._filters('/my/players?team_id=%s' % self.team_a.id)
        summary = ' '.join(details.xpath('./summary')[0].text_content().split())
        self.assertEqual(summary, 'Filtres (1)')

    def test_event_emails_break_at_at(self):
        self._login_tp()
        text, tree = self._get('/my/event/%s' % self.event.id)
        staff = tree.xpath('//*[@data-sc-event-staff]//a[starts-with(@href, "mailto:")]')[0]
        self.assertEqual(staff.text_content(), 'synthetic.therapist.longname@example.com')
        self.assertTrue(staff.xpath('./wbr'))
        org = tree.xpath('//*[@data-sc-event-organization]//a[starts-with(@href, "mailto:")]')[0]
        self.assertEqual(org.text_content(), 'info.synthetic-organization-name@example.com')


@tagged('post_install', '-at_install')
class TestPhoneFiltersEmailTour1743(_Common1743):
    browser_size = '390x844'

    def test_phone_tour(self):
        self.start_tour('/my/players', 'sc_1743_phone_filters', login='pc.tp@example.com')
        self.start_tour('/my/event/%s' % self.event.id, 'sc_1743_event_email', login='pc.tp@example.com')
