"""
Test: Packaging partner-unicity constraint

Acceptance Criteria:
- Two packagings for the same (template, UoM, qty, package_type) but different
  partners are both allowed.
- Creating a third packaging that exactly duplicates an existing
  (template, UoM, qty, package_type, partner) tuple raises ValidationError.
- A packaging with partner_id=False (generic) is treated as its own distinct
  slot; two generic packagings with the same (template, UoM, qty, package_type)
  are rejected.
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools.misc import mute_logger


class TestPartnerUnicity(TransactionCase):
    """Test partner-aware unicity on product.uom.packaging."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create({"name": "Ink Base"})
        cls.tmpl = cls.product.product_tmpl_id
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
        cls.pkg_drum = cls.env["stock.package.type"].create(
            {"name": "205L Drum", "max_weight": 200}
        )
        cls.vendor_a = cls.env["res.partner"].create({"name": "Vendor A"})
        cls.vendor_b = cls.env["res.partner"].create({"name": "Vendor B"})

    def _make_packaging(self, partner=False, qty=100.0, name=None):
        vals = {
            "product_tmpl_id": self.tmpl.id,
            "uom_id": self.uom_kg.id,
            "qty": qty,
            "package_type_id": self.pkg_drum.id,
        }
        if partner:
            vals["partner_id"] = partner.id
        if name:
            vals["name"] = name
        return self.env["product.uom.packaging"].create(vals)

    def test_different_vendors_same_config_allowed(self):
        """Same (tmpl, uom, qty, pkg_type) with different vendors: both succeed."""
        pkg_a = self._make_packaging(
            partner=self.vendor_a, name="Vendor A Drum"
        )
        pkg_b = self._make_packaging(
            partner=self.vendor_b, name="Vendor B Drum"
        )
        self.assertTrue(pkg_a.exists())
        self.assertTrue(pkg_b.exists())

    @mute_logger("odoo.sql_db")
    def test_duplicate_vendor_config_rejected(self):
        """Creating a second packaging with same (tmpl, uom, qty, pkg_type, vendor)
        raises ValidationError."""
        self._make_packaging(partner=self.vendor_a, name="Vendor A Drum First")
        with self.assertRaises(ValidationError):
            self._make_packaging(
                partner=self.vendor_a, name="Vendor A Drum Duplicate"
            )

    @mute_logger("odoo.sql_db")
    def test_duplicate_generic_config_rejected(self):
        """Creating a second generic (partner_id=False) packaging with same
        (tmpl, uom, qty, pkg_type) raises ValidationError."""
        self._make_packaging(name="Generic Drum First")
        with self.assertRaises(ValidationError):
            self._make_packaging(name="Generic Drum Duplicate")

    def test_vendor_and_generic_coexist(self):
        """A generic packaging and a vendor-specific packaging for the same
        (tmpl, uom, qty, pkg_type) can coexist."""
        generic = self._make_packaging(name="Generic Drum")
        vendor = self._make_packaging(
            partner=self.vendor_a, name="Vendor A Drum"
        )
        self.assertTrue(generic.exists())
        self.assertTrue(vendor.exists())
