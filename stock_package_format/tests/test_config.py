# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""UC15 -- Configuration of the package rule.

Acceptance criteria
-------------------
* Flagging a category turns the rule on for its products (``uses_package_rule``).
* A product override « never » / « always » wins over the category.
* Turning the rule on for a product that is not lot-tracked, or that has no
  format unit with a package type, is refused (category flag and override).
* The formats of a product are its packaging units that carry a package type,
  smallest first.
* Unflagged products behave exactly as core: whole-package reservation and the
  no-split guard do not apply (regression guard).
"""

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tools.misc import mute_logger

from .common import PackageFormatCase


class TestPackageRuleConfig(PackageFormatCase):
    def test_category_flag_turns_rule_on(self):
        self.assertTrue(self.product.uses_package_rule)
        self.categ.package_rule = False
        self.assertFalse(self.product.uses_package_rule)

    def test_override_wins_over_category(self):
        self.product.package_rule_override = "never"
        self.assertFalse(self.product.uses_package_rule)
        self.product.package_rule_override = "inherit"
        self.assertTrue(self.product.uses_package_rule)
        self.categ.package_rule = False
        self.product.package_rule_override = "always"
        self.assertTrue(self.product.uses_package_rule)

    def test_flag_requires_lot_tracking(self):
        untracked = self.env["product.product"].create(
            {
                "name": "Untracked Resin Z",
                "is_storable": True,
                "uom_id": self.uom_ft3.id,
                "uom_ids": [Command.set([self.uom_bag.id])],
            }
        )
        with mute_logger("odoo.sql_db"), self.assertRaises(ValidationError):
            untracked.package_rule_override = "always"
        other_categ = self.env["product.category"].create({"name": "Other (test)"})
        untracked.categ_id = other_categ
        with self.assertRaises(ValidationError):
            other_categ.package_rule = True

    def test_flag_requires_format_with_package_type(self):
        no_format = self.env["product.product"].create(
            {
                "name": "Formatless Resin W",
                "is_storable": True,
                "tracking": "lot",
                "uom_id": self.uom_ft3.id,
            }
        )
        with self.assertRaises(ValidationError):
            no_format.package_rule_override = "always"

    def test_cannot_untrack_flagged_product(self):
        with self.assertRaises(ValidationError):
            self.product.tracking = "none"

    def test_formats_sorted_smallest_first(self):
        self.assertEqual(
            self.product._package_format_uoms(),
            self.uom_bag | self.uom_drum | self.uom_bulk,
        )
        self.assertEqual(
            self.product._package_format_uoms().mapped("id"),
            [self.uom_bag.id, self.uom_drum.id, self.uom_bulk.id],
        )

    def test_unflagged_product_reserves_like_core(self):
        # A plain product in packages: core splits a package freely.
        package = self.env["stock.package"].create(
            {"package_type_id": self.type_drum.id}
        )
        self.env["stock.quant"]._update_available_quantity(
            self.plain_product, self.stock, 5.0, package_id=package
        )
        delivery = self._delivery(3.0, self.uom_ft3, product=self.plain_product)
        self.assertEqual(delivery.move_ids.quantity, 3.0)
        delivery.button_validate()
        self.assertEqual(delivery.state, "done")
        self.assertEqual(package.quant_ids.quantity, 2.0)
