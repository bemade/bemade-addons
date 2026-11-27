"""Task 1795, review round 2 (2026-11-27) — a client's « Mon compte »
requires the country again. Synthetic fixtures only.

The app's relaxed address rules (name and email only, a partial address
saved, task 1018c) were deliberate and stay; for a client (the client app)
only the country becomes required.

Acceptance criteria covered here:

* UC-A1 A client's address save without a country is refused (``country_id``
  flagged, nothing written); with a country it is saved, the rest of the
  address still optional (no street, no zip).
* UC-A2 ``/my/address/country_info`` lists ``country_id`` as required for a
  client (the page marks it), not for a coach.
* UC-A3 Staff keep the relaxed rules: a coach saves without a country.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_account_security_shell_1620 import SAVED_URL
from odoo.addons.bemade_sports_clinic.tests.test_review_fixes_1018c import Account1018cCommon


@tagged('post_install', '-at_install')
class TestClientAccountCountry1795(Account1018cCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)
        self.client_partner = self.plain.partner_id
        self.client_partner.sudo().write({
            'email': self.plain.login, 'country_id': False, 'state_id': False,
            'street': False, 'city': False, 'zip': False,
        })

    # -- UC-A1 -----------------------------------------------------------
    def test_client_save_without_country_refused(self):
        self._login_plain()
        result = self._address_post(self.client_partner, city='Synthetic Town', country_id='',
                                    company_name=None, vat=None)
        self.assertNotIn('redirectUrl', result, result)
        self.assertIn('country_id', result.get('invalid_fields', []), result)
        self.client_partner.invalidate_recordset()
        self.assertFalse(self.client_partner.city)

    def test_client_save_with_country(self):
        self._login_plain()
        result = self._address_post(self.client_partner, city='Synthetic Town', street='', zip='',
                                    country_id=str(self.ca.id), company_name=None, vat=None)
        self.assertEqual(result, {'redirectUrl': SAVED_URL}, result)
        self.client_partner.invalidate_recordset()
        self.assertEqual(self.client_partner.country_id, self.ca)
        self.assertEqual(self.client_partner.city, 'Synthetic Town')
        self.assertFalse(self.client_partner.street)

    # -- UC-A2 -----------------------------------------------------------
    def test_country_info_marks_country_for_client_only(self):
        self._login_plain()
        self.assertEqual(sorted(self._country_info(self.ca)['required_fields']),
                         ['country_id', 'email', 'name'])
        self._login_coach()
        self.assertEqual(sorted(self._country_info(self.ca)['required_fields']), ['email', 'name'])

    # -- UC-A3 -----------------------------------------------------------
    def test_staff_keep_relaxed_rules(self):
        self._login_coach()
        partner = self.coach.partner_id
        result = self._address_post(partner, country_id='', state_id='', street='', city='',
                                    company_name=None, vat=None)
        self.assertEqual(result, {'redirectUrl': SAVED_URL}, result)
        partner.invalidate_recordset()
        self.assertFalse(partner.country_id)
