# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""UC1, UC2, UC3, UC11, UC12 -- Receiving into packages in one action.

Acceptance criteria
-------------------
UC1  Receiving 4 × drum (one lot L1) and validating opens the pack dialog;
     confirming it creates 4 drum packages of 5 ft³, each holding lot L1, and
     the receipt is done. The package labels come back as ONE print action
     covering the 4 packages.
UC2  Receiving 42 × bag split 30 lot A + 12 lot B gives 42 bag packages, each
     holding exactly one lot (30 with A, 12 with B).
UC3  A receipt line of 42 ft³ in the base unit asks for the format, defaulting
     to the smallest one (bag); choosing bulk gives 1 bulk package of 42 ft³.
     A quantity that is not a whole number of packages is refused; rows that
     do not add up to the line are refused; a row without a lot is refused.
     « Pack by format » packs without validating.
UC11 A customer return of an unopened drum comes back as one whole drum
     package with its original lot (format and lot prefilled from the
     returned delivery).
UC12 A dropship-like transfer (vendor straight to customer) creates no
     package and asks nothing.
"""

from odoo.exceptions import UserError
from odoo.tests import Form

from .common import PackageFormatCase


class TestReceiptPacking(PackageFormatCase):
    def _packages_in_stock(self, package_type):
        quants = self.env["stock.quant"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "=", self.stock.id),
                ("package_id.package_type_id", "=", package_type.id),
            ]
        )
        return quants

    def test_uc1_receive_drums_one_lot(self):
        receipt = self._receipt(4, self.uom_drum)
        action = receipt.button_validate()
        self.assertEqual(action["res_model"], "stock.package.format.pack.wizard")
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.format_uom_id, self.uom_drum)
        self.assertEqual(wizard.line_ids.package_count, 4)
        wizard.line_ids.lot_name = "L1"
        result = wizard.action_confirm()
        self.assertEqual(receipt.state, "done")
        quants = self._packages_in_stock(self.type_drum)
        self.assertEqual(len(quants), 4)
        self.assertEqual(len(quants.package_id), 4)
        self.assertEqual(set(quants.mapped("quantity")), {5.0})
        self.assertEqual(quants.lot_id.name, "L1")
        self.assertEqual(len(set(quants.package_id.mapped("name"))), 4)
        # Labels: one batch for the four packages.
        self.assertEqual(result["tag"], "do_multi_print")
        reports = result["params"]["reports"]
        self.assertEqual(len(reports), 1)
        self.assertEqual(
            sorted(reports[0]["context"]["active_ids"]), sorted(quants.package_id.ids)
        )

    def test_uc2_receive_bags_two_lots(self):
        receipt = self._receipt(42, self.uom_bag)
        action = receipt.button_validate()
        self._run_pack_wizard(
            action, rows=[(self.uom_bag, 30, "LOT-A"), (self.uom_bag, 12, "LOT-B")]
        )
        self.assertEqual(receipt.state, "done")
        quants = self._packages_in_stock(self.type_bag)
        self.assertEqual(len(quants.package_id), 42)
        for package in quants.package_id:
            self.assertEqual(len(package.quant_ids.lot_id), 1)
        self.assertEqual(
            len(quants.filtered(lambda q: q.lot_id.name == "LOT-A")), 30
        )
        self.assertEqual(
            len(quants.filtered(lambda q: q.lot_id.name == "LOT-B")), 12
        )

    def test_uc3_plain_unit_asks_format(self):
        receipt = self._receipt(42, self.uom_ft3)
        action = receipt.button_validate()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        with Form(wizard) as form:
            with form.line_ids.edit(0) as row:
                self.assertEqual(row.format_uom_id, self.uom_bag)
                self.assertEqual(row.package_count, 42)
                row.format_uom_id = self.uom_bulk
                self.assertEqual(row.package_count, 1)
                row.lot_name = "L3"
        wizard.action_confirm()
        self.assertEqual(receipt.state, "done")
        quants = self._packages_in_stock(self.type_bulk)
        self.assertEqual(len(quants), 1)
        self.assertEqual(quants.quantity, 42.0)

    def test_uc3_refuses_partial_package(self):
        receipt = self._receipt(7, self.uom_ft3)
        action = receipt.button_validate()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        wizard.line_ids.write(
            {"format_uom_id": self.uom_drum.id, "package_count": 1, "lot_name": "L"}
        )
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertNotEqual(receipt.state, "done")

    def test_uc3_refuses_row_without_lot(self):
        receipt = self._receipt(2, self.uom_drum)
        action = receipt.button_validate()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        wizard.line_ids.lot_name = False
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_pack_by_format_button_does_not_validate(self):
        receipt = self._receipt(2, self.uom_drum)
        action = receipt.action_package_format_pack()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        wizard.line_ids.lot_name = "L9"
        wizard.action_confirm()
        self.assertNotEqual(receipt.state, "done")
        self.assertEqual(len(receipt.move_line_ids.result_package_id), 2)
        # Validating now needs no dialog any more.
        receipt.button_validate()
        self.assertEqual(receipt.state, "done")
        self.assertEqual(len(self._packages_in_stock(self.type_drum)), 2)

    def test_uc11_customer_return_whole_drum(self):
        self._put_packages(self.uom_drum, 1, lot_name="L1")
        delivery = self._delivery(1, self.uom_drum)
        delivery.button_validate()
        self.assertEqual(delivery.state, "done")
        wizard = (
            self.env["stock.return.picking"]
            .with_context(active_id=delivery.id, active_model="stock.picking")
            .create({"picking_id": delivery.id})
        )
        wizard.product_return_moves.quantity = 1
        res = wizard.action_create_returns()
        ret = self.env["stock.picking"].browse(res["res_id"])
        action = ret.button_validate()
        if isinstance(action, dict) and action.get("res_model"):
            pack = self.env[action["res_model"]].browse(action["res_id"])
            self.assertEqual(pack.line_ids.format_uom_id, self.uom_drum)
            self.assertEqual(pack.line_ids.lot_name, "L1")
            pack.action_confirm()
        self.assertEqual(ret.state, "done")
        quants = self._packages_in_stock(self.type_drum)
        self.assertEqual(len(quants), 1)
        self.assertEqual(quants.quantity, 5.0)
        self.assertEqual(quants.lot_id.name, "L1")

    def test_uc12_dropship_creates_no_package(self):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.in_type_id.id,
                "location_id": self.supplier_loc.id,
                "location_dest_id": self.customer_loc.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 2,
                            "product_uom": self.uom_drum.id,
                            "location_id": self.supplier_loc.id,
                            "location_dest_id": self.customer_loc.id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_line_ids.lot_name = "LD"
        result = picking.button_validate()
        self.assertIs(result, True)
        self.assertEqual(picking.state, "done")
        self.assertFalse(picking.move_line_ids.result_package_id)
