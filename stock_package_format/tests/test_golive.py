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
UC14b « Pack the rest as »: a format (default: the product's smallest
     format) and a lot (prefilled from the lot of the last row, editable).
     After the explicit rows, the remaining loose free stock is packed into as
     many WHOLE packages of that format as fit; a leftover smaller than one
     package stays loose. The dialog shows how many rest packages will be
     created and the leftover. Works without any row. A lot is required when
     a rest will be packed. An empty rest format packs nothing more.
Rep  The product shows a summary of its packages per format (unopened count,
     opened count and their content), and the quant report can be grouped by
     package type and lot.
"""

from odoo.exceptions import UserError
from odoo.tests import Form

from odoo.fields import Command

from .common import PackageFormatCase


class TestGoLive(PackageFormatCase):
    def _wizard(self, rows, location=None, rest_format=False, rest_lot=None):
        vals = {
            "product_id": self.product.id,
            "location_id": (location or self.stock).id,
            "line_ids": [
                Command.create({"format_uom_id": uom.id, "package_count": n, "lot_name": lot})
                for uom, n, lot in rows
            ],
        }
        if rest_format is not None:
            vals["rest_format_uom_id"] = rest_format and rest_format.id
        if rest_lot is not None:
            vals["rest_lot_name"] = rest_lot
        return self.env["stock.package.format.golive.wizard"].create(vals)

    def _quants(self):
        return self.env["stock.quant"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "=", self.stock.id),
                ("quantity", ">", 0),
            ]
        )

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
        self.assertEqual(len(set(packed.package_id.mapped("name"))), 40)
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

    def test_uc14b_rest_defaults_in_the_dialog(self):
        self._put_loose(126.0)
        with Form(
            self.env["stock.package.format.golive.wizard"].with_context(
                default_product_id=self.product.id
            )
        ) as form:
            self.assertEqual(form.location_id, self.stock)
            self.assertEqual(form.rest_format_uom_id, self.uom_bag)  # smallest format
            with form.line_ids.new() as row:
                row.format_uom_id = self.uom_drum
                row.package_count = 2
                row.lot_name = "GL-D"
            with form.line_ids.new() as row:
                row.format_uom_id = self.uom_bulk
                row.package_count = 1
                row.lot_name = "GL-S"
            self.assertEqual(form.rest_lot_name, "GL-S")  # lot of the last row
            self.assertEqual(form.rest_package_count, 74)
            self.assertEqual(form.rest_leftover, 0.0)
            form.rest_lot_name = "GL-B"  # editable
            form.rest_format_uom_id = self.uom_drum
            self.assertEqual(form.rest_package_count, 14)
            self.assertAlmostEqual(form.rest_leftover, 4.0)
            self.assertEqual(form.rest_lot_name, "GL-B")

    def test_uc14b_rows_and_rest(self):
        self._put_loose(126.0)
        wizard = self._wizard(
            [(self.uom_drum, 2, "GL-D"), (self.uom_bulk, 1, "GL-S")],
            rest_format=None,  # default: the smallest format
            rest_lot="GL-B",
        )
        self.assertEqual(wizard.rest_format_uom_id, self.uom_bag)
        self.assertEqual(wizard.rest_package_count, 74)
        wizard.action_confirm()
        quants = self._quants()
        self.assertTrue(all(q.package_id for q in quants))
        self.assertEqual(sum(quants.mapped("quantity")), 126.0)
        bags = quants.filtered(lambda q: q.package_id.package_type_id == self.type_bag)
        self.assertEqual(len(bags.package_id), 74)
        self.assertEqual(bags.lot_id.name, "GL-B")
        self.assertEqual(
            len(quants.filtered(lambda q: q.package_id.package_type_id == self.type_drum)), 2
        )

    def test_uc14b_rest_only_without_rows(self):
        self._put_loose(12.5)
        wizard = self._wizard([], rest_format=self.uom_drum, rest_lot="R1")
        self.assertEqual(wizard.rest_package_count, 2)
        self.assertAlmostEqual(wizard.rest_leftover, 2.5)
        wizard.action_confirm()
        quants = self._quants()
        packed = quants.filtered("package_id")
        self.assertEqual(len(packed.package_id), 2)
        self.assertEqual(packed.package_id.package_type_id, self.type_drum)
        self.assertEqual(packed.lot_id.name, "R1")
        self.assertAlmostEqual(sum(quants.filtered(lambda q: not q.package_id).mapped("quantity")), 2.5)

    def test_uc14b_leftover_below_one_package_stays_loose(self):
        self._put_loose(7.4)
        wizard = self._wizard([], rest_format=self.uom_bag, rest_lot="R2")
        self.assertEqual(wizard.rest_package_count, 7)
        self.assertAlmostEqual(wizard.rest_leftover, 0.4)
        wizard.action_confirm()
        quants = self._quants()
        self.assertEqual(len(quants.filtered("package_id").package_id), 7)
        loose = quants.filtered(lambda q: not q.package_id)
        self.assertAlmostEqual(sum(loose.mapped("quantity")), 0.4)

    def test_uc14b_rest_needs_a_lot(self):
        self._put_loose(10.0)
        wizard = self._wizard([], rest_format=self.uom_bag, rest_lot="")
        self.assertEqual(wizard.rest_package_count, 10)
        with self.assertRaises(UserError):
            wizard.action_confirm()
        # nothing to pack as rest: no lot needed
        self._put_loose(-9.5)
        wizard = self._wizard([], rest_format=self.uom_bag, rest_lot="")
        self.assertEqual(wizard.rest_package_count, 0)
        wizard.action_confirm()
        self.assertFalse(self._quants().filtered("package_id"))

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
