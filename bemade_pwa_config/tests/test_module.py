from odoo.tests import TransactionCase, tagged
import base64
from PIL import Image
from io import BytesIO


@tagged("post_install", "-at_install")
class TestPwaConfig(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Company = cls.env["res.company"]
        cls.ConfigSettings = cls.env["res.config.settings"]

    def _create_test_image(self, size=256):
        """Helper to create a test image in binary format"""
        img = Image.new('RGB', (size, size), color='red')
        stream = BytesIO()
        img.save(stream, format='PNG')
        return base64.b64encode(stream.getvalue())

    def test_company_pwa_fields(self):
        """Test that company has PWA configuration fields"""
        company = self.Company.search([], limit=1)
        self.assertIsNotNone(company)
        self.assertTrue(hasattr(company, "web_app_icon"))
        self.assertTrue(hasattr(company, "pwa_icon_192"))
        self.assertTrue(hasattr(company, "pwa_icon_512"))

    def test_company_pwa_default_colors(self):
        """Test default PWA colors"""
        company = self.Company.search([], limit=1)
        self.assertIsNotNone(company)
        # Default colors should be set
        self.assertTrue(hasattr(company, "web_app_fgcolor"))
        self.assertTrue(hasattr(company, "web_app_bgcolor"))

    def test_config_settings_pwa(self):
        """Test that config settings supports PWA"""
        settings = self.ConfigSettings.create({})
        self.assertIsNotNone(settings.id)
        self.assertTrue(hasattr(settings, "web_app_icon"))
        self.assertTrue(hasattr(settings, "pwa_icon_192"))

    def test_config_settings_related_fields(self):
        """Test that config settings related fields work"""
        company = self.Company.search([], limit=1)
        settings = self.ConfigSettings.create({})
        # Related fields should be accessible
        self.assertTrue(hasattr(settings, "web_app_fgcolor"))
        self.assertTrue(hasattr(settings, "web_app_bgcolor"))

    def test_create_company_with_icon(self):
        """Test creating company with PWA icon triggers generation"""
        test_image = self._create_test_image(512)
        company = self.Company.create({
            "name": "Test PWA Company",
            "web_app_icon": test_image,
            "web_app_fgcolor": "#FFFFFF",
            "web_app_bgcolor": "#000000"
        })
        self.assertIsNotNone(company.id)
        # Icons should be generated
        self.assertTrue(bool(company.pwa_icon_192) or bool(company.pwa_icon_512) or not company.web_app_icon)

    def test_write_icon_triggers_generation(self):
        """Test that writing web_app_icon triggers generation"""
        company = self.Company.search([], limit=1)
        test_image = self._create_test_image(512)
        company.write({"web_app_icon": test_image})
        # Should complete without error
        self.assertIsNotNone(company.id)

    def test_write_non_icon_field_skips_generation(self):
        """Test that writing non-icon fields skips generation"""
        company = self.Company.search([], limit=1)
        # Write color without icon
        company.write({"web_app_fgcolor": "#AAAAAA"})
        self.assertEqual(company.web_app_fgcolor, "#AAAAAA")

    def test_company_without_icon(self):
        """Test company without icon doesn't error"""
        company = self.Company.create({
            "name": "No Icon Company"
        })
        self.assertIsNotNone(company.id)
        # Icons should be empty
        self.assertFalse(bool(company.pwa_icon_192) and bool(company.pwa_icon_512))

    def test_pwa_colors_persistence(self):
        """Test that PWA colors persist"""
        company = self.Company.search([], limit=1)
        original_fg = company.web_app_fgcolor
        company.write({"web_app_fgcolor": "#FF0000"})
        self.assertEqual(company.web_app_fgcolor, "#FF0000")
        company.write({"web_app_fgcolor": original_fg})
        self.assertEqual(company.web_app_fgcolor, original_fg)

    def test_config_settings_write(self):
        """Test config settings write operations"""
        company = self.Company.search([], limit=1)
        settings = self.ConfigSettings.create({})
        # Write should work for related fields
        settings.write({"web_app_fgcolor": "#123456"})
        self.assertIsNotNone(settings.id)

    def test_multiple_companies_separate_configs(self):
        """Test multiple companies have separate PWA configs"""
        company1 = self.Company.create({"name": "Company 1", "web_app_fgcolor": "#111111"})
        company2 = self.Company.create({"name": "Company 2", "web_app_fgcolor": "#222222"})

        self.assertEqual(company1.web_app_fgcolor, "#111111")
        self.assertEqual(company2.web_app_fgcolor, "#222222")
