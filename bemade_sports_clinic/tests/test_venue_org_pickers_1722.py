"""Task 1722 — the event form's Venue and Organisation are type-to-filter
pickers (the #1648 picker the « Équipe » links use). Synthetic fixtures.

Acceptance criteria:

* AC-1 Create / edit form: ``select[name=venue_id]`` and
  ``select[name=organization_id]`` carry ``data-sc-picker`` (keys venue /
  org) and ``data-sc-picker-empty`` — « To be determined » / « All
  organizations » stay the first, choosable option; the posted field
  names are unchanged; the « New venue » sheet stays.
* AC-2 The event page's edit card: the venue autosave select is a picker.
* AC-3 Browser: type part of a venue name (accents ignored) → pick → the
  event is saved with it; the organisation picked by typing narrows the
  teams (#1597's groupSelect follows the select's change); « To be
  determined » can be picked back.
* AC-4 Server: the posted values are unchanged (same names).

Filters: the events / calendar filters' Organisation is already a picker
(#1648); they have no venue filter. Real taps stay UNVERIFIED until
/dev-review.
"""
import json

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_event_org_team_filter_1597 import Org1597Common


@tagged('post_install', '-at_install')
class TestVenueOrgPickers1722(Org1597Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.venue = cls.env['res.partner'].create({
            'name': 'Aréna Synthétique-Côté', 'is_company': True, 'is_venue': True})
        cls.venue2 = cls.env['res.partner'].create({
            'name': 'Centre Synthe Nord', 'is_company': True, 'is_venue': True})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def test_form_selects_are_pickers(self):
        self._login_cadmin()
        form = self._form()
        venue = form.xpath('.//select[@name="venue_id"]')[0]
        self.assertEqual(venue.get('data-sc-picker'), '1')
        self.assertEqual(venue.get('data-sc-picker-key'), 'venue')
        self.assertEqual(venue.get('data-sc-picker-empty'), '1')
        first = venue.xpath('./option')[0]
        self.assertEqual((first.get('value'), first.text_content().strip()), ('', 'To be determined'))
        self.assertTrue(form.xpath('.//button[@data-sc-sheet-open="sc_venue_sheet"]'))
        org = form.xpath('.//select[@name="organization_id"]')[0]
        self.assertEqual((org.get('data-sc-picker'), org.get('data-sc-picker-key'), org.get('data-sc-picker-empty')),
                         ('1', 'org', '1'))
        self.assertEqual(org.xpath('./option')[0].get('value'), '')

    def test_event_card_venue_is_a_picker(self):
        self._login_tp()
        _text, tree = self._get('/my/event/%s' % self.event.id)
        for node in tree.xpath('//owl-component[@props]'):
            props = json.loads(node.get('props'))
            if props.get('field') == 'venue_id' and props.get('model') == 'sports.event':
                self.assertTrue(props.get('picker'))
                self.assertEqual(props.get('pickerKey'), 'venue')
                return
        self.fail('no venue field on the event card')


@tagged('post_install', '-at_install')
class TestVenueOrgPickersTour1722(Org1597Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.venue = cls.env['res.partner'].create({
            'name': 'Aréna Synthétique-Côté', 'is_company': True, 'is_venue': True})

    def test_create_with_typed_venue_and_org(self):
        self._switch(True)
        self.start_tour('/my/event/create', 'sc_1722_venue_org_pickers', login='p77.cadmin@example.com')
        event = self.env['sports.event'].search([('name', '=', 'SC 1722 Tour')])
        self.assertEqual(len(event), 1)
        self.assertEqual(event.venue_id, self.venue)
        self.assertEqual(event.team_ids, self.team_c)
