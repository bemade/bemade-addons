# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""UC14 and reporting -- Go-live packing of existing stock, stock summary.

Acceptance criteria
-------------------
UC14 « Pack existing stock » on a product, for a location, with rows of
     N × format + lot, packs loose stock (with or without a lot) into N
     packages of the format, each holding its lot, through an inventory
     adjustment. The product total does not change. Asking more than the
     free loose stock is refused. Old loose stock not packed stays usable as
     loose.
Rep  The product shows a summary of its packages per format (unopened count,
     opened count and their content), and the quant report can be grouped by
     package type and lot.
"""

from odoo.exceptions import UserError

from .common import PackageFormatCase


class TestGoLive(PackageFormatCase):
    def _wizard(self, rows, location=None):
        wizard = self.env["stock.package.format.golive.wizard"].create(
            {
                "product_id": self.product.id,
                "location_id": (location or self.stock).id,
                "line_ids": [
                    (0, 0, {"format_uom_id": uom.id, "package_count": n, "lot_name": lot})
                    for uom, n, lot in rows
                ],
            }
        )
        return wizard

    def test_uc14_pack_existing_loose_stock(self):
        self._put_loose(126.0)  # untracked legacy stock, no lot
        wizard = self._wizard(
            [(self.uom_drum, 20, "LEGACY-1"), (self.uom_bag, 20, "LEGACY-2")]
        )
        self.assertEqual(wizard.loose_quantity, 126.0)
        wizard.action_confirm()
        quants = self.env["stock.quant"].search(
            [("product_id", "=", self.product.id), ("location_id", "=", self.stock.id)]
        )
        packed = quants.filtered("package_id")
        self.assertEqual(len(packed.package_id), 40)
        self.assertEqual(
            len(packed.filtered(lambda q: q.package_id.package_type_id == self.type_drum)), 20
        )
        self.assertEqual(sum(packed.mapped("quantity")), 120.0)
        self.assertEqual(sum(quants.mapped("quantity")), 126.0)
        loose = quants.filtered(lambda q: not q.package_id)
        self.assertEqual(sum(loose.mapped("quantity")), 6.0)
        # the 6 ft³ left loose are still usable by a loose move
        delivery = self._delivery(6, self.uom_ft3)
        self.assertEqual(delivery.move_ids.quantity, 6)

    def test_uc14_refuses_more_than_loose_stock(self):
        self._put_loose(4.0)
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        wizard = self._wizard([(self.uom_drum, 1, "X")])
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_uc14_lot_tracked_loose_stock(self):
        self._put_loose(10.0, lot_name="OLD")
        self._wizard([(self.uom_drum, 2, "OLD")]).action_confirm()
        quants = self.env["stock.quant"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "=", self.stock.id),
                ("quantity", ">", 0),
            ]
        )
        self.assertEqual(len(quants), 2)
        self.assertEqual(quants.lot_id.name, "OLD")
        self.assertTrue(all(q.package_id for q in quants))

    def test_summary_on_product(self):
        self._put_packages(self.uom_bag, 12, lot_name="L1")
        self._put_packages(self.uom_drum, 3, lot_name="L2")
        opened = self._put_packages(self.uom_drum, 1, lot_name="L2", opened=True)
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.stock, -3.2, lot_id=self._lot("L2"), package_id=opened
        )
        summary = self.product.product_tmpl_id.package_format_summary
        self.assertIn("12 × %s" % self.type_bag.name, summary)
        self.assertIn("3 × %s" % self.type_drum.name, summary)
        self.assertIn("1.8", summary)
        groups = self.env["stock.quant"]._read_group(
            [("product_id", "=", self.product.id), ("quantity", ">", 0)],
            ["package_type_id", "package_is_opened", "lot_id"],
            ["quantity:sum"],
        )
        self.assertEqual(len(groups), 3)
