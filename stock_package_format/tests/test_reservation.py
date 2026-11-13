# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""UC4 (stock side), UC6, UC10 -- Reservation takes whole packages only.

Acceptance criteria
-------------------
UC4  A delivery of 2 × drum with 3 drums + 40 bags in stock reserves 2 whole
     drum packages (10 ft³), never bags.
UC6  A delivery of 2 × drum with 1 drum + 1 opened drum (3 ft³ left) reserves
     the unopened drum only; the opened drum is never used by a format move.
     Partial availability counts whole packages only.
*    A delivery in the base unit (loose) reserves loose stock and opened
     packages only, never unopened packages.
*    A package partly reserved elsewhere is not free for a format move.
*    Unreserving frees whole packages; a re-reservation through
     ``stock.move._update_reserved_quantity`` (the path used by custom
     re-reserve code) obeys the same rule.
*    Validating a transfer that takes part of an unopened package is refused.
UC10 An internal transfer to another warehouse moves whole packages: the drum
     packages arrive in the destination location still packed, lot kept.
"""

from odoo.exceptions import UserError

from .common import PackageFormatCase


class TestWholePackageReservation(PackageFormatCase):
    def test_uc4_format_move_takes_whole_packages_of_its_format(self):
        drums = self._put_packages(self.uom_drum, 3, lot_name="L1")
        self._put_packages(self.uom_bag, 40, lot_name="L2")
        delivery = self._delivery(2, self.uom_drum)
        move = delivery.move_ids
        self.assertEqual(move.state, "assigned")
        self.assertEqual(move.quantity, 2)
        self.assertEqual(len(move.move_line_ids), 2)
        self.assertTrue(move.move_line_ids.package_id <= drums)
        self.assertEqual(sum(move.move_line_ids.mapped("quantity_product_uom")), 10)

    def test_uc6_opened_drum_never_used_by_format_move(self):
        drum = self._put_packages(self.uom_drum, 1, lot_name="L1")
        opened = self._put_packages(self.uom_drum, 1, lot_name="L1", opened=True)
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.stock, -2.0, lot_id=self._lot("L1"), package_id=opened
        )
        delivery = self._delivery(2, self.uom_drum)
        move = delivery.move_ids
        self.assertEqual(move.state, "partially_available")
        self.assertEqual(move.quantity, 1)
        self.assertEqual(move.move_line_ids.package_id, drum)

    def test_loose_move_uses_loose_and_opened_only(self):
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        opened = self._put_packages(self.uom_bag, 1, lot_name="L2", opened=True)
        self._put_loose(1.5, lot_name="L3")
        delivery = self._delivery(4, self.uom_ft3)
        move = delivery.move_ids
        self.assertEqual(move.state, "partially_available")
        self.assertAlmostEqual(move.quantity, 2.5)
        packages = move.move_line_ids.package_id
        self.assertEqual(packages, opened)

    def test_partly_reserved_package_is_not_free(self):
        drum = self._put_packages(self.uom_drum, 1, lot_name="L1", opened=True)
        loose_delivery = self._delivery(1, self.uom_ft3)
        self.assertEqual(loose_delivery.move_ids.move_line_ids.package_id, drum)
        drum.is_opened = False  # someone closed it again: still not free
        delivery = self._delivery(1, self.uom_drum)
        self.assertEqual(delivery.move_ids.quantity, 0)

    def test_unreserve_and_rereserve_path(self):
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        self._put_packages(self.uom_bag, 10, lot_name="L2")
        delivery = self._delivery(3, self.uom_drum)
        move = delivery.move_ids
        self.assertEqual(move.quantity, 2)
        delivery.do_unreserve()
        self.assertEqual(move.quantity, 0)
        self.assertEqual(self._free_qty(), 20.0)
        # Custom re-reserve code calls _update_reserved_quantity directly.
        taken = move._update_reserved_quantity(15.0, move.location_id)
        self.assertEqual(taken, 10.0)
        self.assertEqual(len(move.move_line_ids.package_id), 2)
        self.assertEqual(move.move_line_ids.package_id.package_type_id, self.type_drum)

    def test_validating_part_of_unopened_package_is_refused(self):
        self._put_packages(self.uom_drum, 1, lot_name="L1")
        delivery = self._delivery(1, self.uom_drum)
        delivery.move_ids.move_line_ids.quantity = 0.6  # 3 ft³ of the drum
        delivery.move_ids.picked = True
        with self.assertRaises(UserError):
            delivery.with_context(skip_backorder=True).button_validate()

    def test_full_delivery_and_backorder_whole_packages(self):
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        delivery = self._delivery(3, self.uom_drum)
        backorder_wizard = delivery.button_validate()
        if isinstance(backorder_wizard, dict) and backorder_wizard.get("res_model"):
            self.env[backorder_wizard["res_model"]].with_context(
                **backorder_wizard["context"]
            ).create({}).process()
        self.assertEqual(delivery.state, "done")
        self.assertEqual(sum(delivery.move_ids.mapped("quantity")), 2)
        backorder = delivery.backorder_ids
        self.assertEqual(backorder.move_ids.product_uom_qty, 1)
        self._put_packages(self.uom_drum, 1, lot_name="L4")
        backorder.action_assign()
        self.assertEqual(backorder.move_ids.quantity, 1)

    def test_uc10_interwarehouse_transfer_moves_whole_packages(self):
        drums = self._put_packages(self.uom_drum, 2, lot_name="L1")
        wh2 = self.env["stock.warehouse"].create({"name": "Second WH", "code": "WH2T"})
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.int_type_id.id,
                "location_id": self.stock.id,
                "location_dest_id": wh2.lot_stock_id.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 2,
                            "product_uom": self.uom_drum.id,
                            "location_id": self.stock.id,
                            "location_dest_id": wh2.lot_stock_id.id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(picking.move_ids.quantity, 2)
        result = picking.button_validate()
        self.assertIs(result, True)
        self.assertEqual(picking.state, "done")
        quants = self.env["stock.quant"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "=", wh2.lot_stock_id.id),
            ]
        )
        self.assertEqual(quants.package_id, drums)
        self.assertEqual(quants.lot_id.name, "L1")
        self.assertEqual(set(quants.mapped("quantity")), {5.0})
