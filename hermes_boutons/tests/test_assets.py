from odoo.tests import TransactionCase, tagged

HELPER_URL = "/hermes_boutons/static/src/hermes_url.js"
PATCH_URL = "/hermes_boutons/static/src/hermes_boutons.js"
HOOT_TEST_URL = "/hermes_boutons/static/tests/hermes_url.test.js"


@tagged("post_install", "-at_install", "hermes_boutons")
class TestHermesBoutonsAssets(TransactionCase):
    def test_security_helper_and_tests_are_bundled(self):
        backend = self.env["ir.qweb"]._get_asset_bundle("web.assets_backend")
        unit_tests = self.env["ir.qweb"]._get_asset_bundle("web.assets_unit_tests")

        backend_urls = [asset.url for asset in backend.javascripts]
        unit_test_urls = [asset.url for asset in unit_tests.javascripts]
        self.assertIn(HELPER_URL, backend_urls)
        self.assertIn(PATCH_URL, backend_urls)
        self.assertIn(HOOT_TEST_URL, unit_test_urls)
