"""Acceptance criteria — MyCarrier tracking link.

See module docstring of :mod:`delivery_mycarrier` for full contract.

The exact URL pattern is provisional and will be confirmed against the
MyCarrier sandbox. Tests assert the PRO number appears in the URL and
that no PRO ref produces an empty string (never a broken link).
"""

from .common import MyCarrierCommon


class TestMyCarrierTrackingLink(MyCarrierCommon):

    def test_returns_url_with_pro_number(self):
        picking = self.make_picking()
        picking.carrier_tracking_ref = "PRO987654"
        url = self.carrier.mycarrier_get_tracking_link(picking)
        self.assertIn("PRO987654", url)
        self.assertIn("mycarrier", url.lower())
        self.assertTrue(url.startswith("https://"))

    def test_returns_empty_when_no_tracking_ref(self):
        picking = self.make_picking()
        picking.carrier_tracking_ref = False
        self.assertEqual(self.carrier.mycarrier_get_tracking_link(picking), "")

    def test_link_contains_no_credentials(self):
        picking = self.make_picking()
        picking.carrier_tracking_ref = "PRO987654"
        url = self.carrier.mycarrier_get_tracking_link(picking)
        self.assertNotIn(self.carrier.sudo().mycarrier_api_key, url)
        self.assertNotIn(self.carrier.sudo().mycarrier_account_email, url)
