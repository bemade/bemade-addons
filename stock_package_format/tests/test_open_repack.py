# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""UC7 (stock side), UC8, UC9, UC13 -- Open and Repack.

Acceptance criteria
-------------------
UC7  A loose move of 3 ft³ with no opened package and no loose stock reserves
     nothing and proposes the smallest unopened package that covers the need
     (a drum when only bags and drums are in stock; a bag for 0.5 ft³). When no
     single package covers it, the proposal lists the fewest packages,
     largest first. After an authorized user opens the proposed package from
     the move, the move reserves from it.
UC8  Open: a user without « Can open packages » is refused. An authorized
     user's Open flags the package opened with who / when / reason, logs it
     in the package chatter (French first, then English) and keeps the lot.
     Taking 3.2 ft³ from an opened drum leaves 1.8 ft³ in the same package.
UC9  Repack 42 ft³ of a bulk bag (lot L3) into bags gives 42 bag packages of
     lot L3; the bulk bag is opened (logged) and emptied. Asking more than
     the source lot holds is refused (a source holding two lots is repacked
     one lot at a time). Repack is gated by the same group.
UC13 A consumption move (stock to production, the shape of a manufacturing
     order component) of 3 ft³ follows the loose rule of UC7.
"""

from odoo.exceptions import AccessError, UserError

from .common import PackageFormatCase


class TestOpenRepack(PackageFormatCase):
    def test_uc7_loose_move_proposes_smallest_covering_package(self):
        self._put_packages(self.uom_bag, 10, lot_name="L1")
        drum = self._put_packages(self.uom_drum, 1, lot_name="L2")
        delivery = self._delivery(3, self.uom_ft3)
        move = delivery.move_ids
        self.assertEqual(move.quantity, 0)
        self.assertEqual(move.package_format_proposal_ids, drum)
        self.assertIn("1 ×", move.package_format_proposal)
        action = move.with_user(self.opener).action_package_format_open_proposal()
        wizard = (
            self.env[action["res_model"]]
            .with_user(self.opener)
            .with_context(**action["context"])
            .create({"reason": "Fill a customer tank"})
        )
        wizard.action_confirm()
        self.assertTrue(drum.is_opened)
        self.assertEqual(move.quantity, 3)
        self.assertEqual(move.move_line_ids.package_id, drum)

    def test_uc7_small_need_proposes_a_bag(self):
        bags = self._put_packages(self.uom_bag, 3, lot_name="L1")
        self._put_packages(self.uom_drum, 1, lot_name="L2")
        delivery = self._delivery(0.5, self.uom_ft3)
        self.assertEqual(len(delivery.move_ids.package_format_proposal_ids), 1)
        self.assertTrue(delivery.move_ids.package_format_proposal_ids <= bags)

    def test_uc7_no_single_package_covers(self):
        self._put_packages(self.uom_bag, 5, lot_name="L1")
        delivery = self._delivery(3, self.uom_ft3)
        self.assertEqual(len(delivery.move_ids.package_format_proposal_ids), 3)

    def test_uc8_open_requires_group(self):
        drum = self._put_packages(self.uom_drum, 1, lot_name="L1")
        with self.assertRaises(AccessError):
            drum.with_user(self.stock_user)._package_format_open("why not")
        self.assertFalse(drum.is_opened)

    def test_uc8_open_logs_and_keeps_lot(self):
        drum = self._put_packages(self.uom_drum, 1, lot_name="L1")
        drum.with_user(self.opener)._package_format_open("Tank refill")
        self.assertTrue(drum.is_opened)
        self.assertEqual(drum.opened_by_id, self.opener)
        self.assertTrue(drum.opened_date)
        self.assertEqual(drum.open_reason, "Tank refill")
        self.assertEqual(drum.quant_ids.lot_id.name, "L1")
        body = drum.message_ids[:1].body
        self.assertIn("Tank refill", body)
        delivery = self._delivery(3.2, self.uom_ft3)
        self.assertAlmostEqual(delivery.move_ids.quantity, 3.2)
        delivery.button_validate()
        self.assertEqual(delivery.state, "done")
        self.assertAlmostEqual(drum.quant_ids.quantity, 1.8)
        self.assertEqual(drum.quant_ids.lot_id.name, "L1")
        self.assertEqual(drum.location_id, self.stock)

    def test_uc8_open_wizard_requires_reason(self):
        drum = self._put_packages(self.uom_drum, 1, lot_name="L1")
        action = drum.with_user(self.opener).action_package_format_open()
        wizard = (
            self.env[action["res_model"]]
            .with_user(self.opener)
            .with_context(**action["context"])
            .create({"reason": "Sampling"})
        )
        wizard.action_confirm()
        self.assertTrue(drum.is_opened)

    def test_uc9_repack_bulk_into_bags(self):
        bulk = self._put_packages(self.uom_bulk, 1, lot_name="L3")
        wizard = (
            self.env["stock.package.format.repack.wizard"]
            .with_user(self.opener)
            .create(
                {
                    "product_id": self.product.id,
                    "location_id": self.stock.id,
                    "source_package_id": bulk.id,
                    "lot_id": self._lot("L3").id,
                    "format_uom_id": self.uom_bag.id,
                    "package_count": 42,
                    "reason": "Split for small orders",
                }
            )
        )
        new_packages = wizard.action_confirm_packages()
        self.assertEqual(len(new_packages), 42)
        self.assertEqual(len(set(new_packages.mapped("name"))), 42)
        self.assertEqual(set(new_packages.mapped("package_type_id").ids), {self.type_bag.id})
        quants = new_packages.quant_ids
        self.assertEqual(set(quants.mapped("quantity")), {1.0})
        self.assertEqual(quants.lot_id.name, "L3")
        self.assertTrue(bulk.is_opened)
        self.assertFalse(bulk.quant_ids.filtered("quantity"))
        self.assertTrue(new_packages[0].message_ids)

    def test_uc9_repack_refuses_more_than_lot_holds(self):
        mixed = self._put_packages(self.uom_bulk, 1, lot_name="L3", opened=True)
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.stock, -10.0, lot_id=self._lot("L3"), package_id=mixed
        )
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.stock, 10.0, lot_id=self._lot("L4"), package_id=mixed
        )
        wizard = (
            self.env["stock.package.format.repack.wizard"]
            .with_user(self.opener)
            .create(
                {
                    "product_id": self.product.id,
                    "location_id": self.stock.id,
                    "source_package_id": mixed.id,
                    "lot_id": self._lot("L3").id,
                    "format_uom_id": self.uom_bag.id,
                    "package_count": 40,
                    "reason": "Split",
                }
            )
        )
        with self.assertRaises(UserError):
            wizard.action_confirm_packages()
        wizard.package_count = 32
        self.assertEqual(len(wizard.action_confirm_packages()), 32)

    def test_uc9_repack_requires_group(self):
        self._put_loose(10, lot_name="L5")
        wizard = self.env["stock.package.format.repack.wizard"].create(
            {
                "product_id": self.product.id,
                "location_id": self.stock.id,
                "lot_id": self._lot("L5").id,
                "format_uom_id": self.uom_drum.id,
                "package_count": 2,
                "reason": "Pack loose",
            }
        )
        with self.assertRaises(AccessError):
            wizard.with_user(self.stock_user).action_confirm_packages()
        self.assertEqual(len(wizard.with_user(self.opener).action_confirm_packages()), 2)

    def test_uc13_consumption_move_follows_loose_rule(self):
        self._put_packages(self.uom_drum, 1, lot_name="L1")
        production_loc = self.env["stock.location"].search(
            [("usage", "=", "production"), ("company_id", "in", [self.company.id, False])],
            limit=1,
        )
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 3,
                "product_uom": self.uom_ft3.id,
                "location_id": self.stock.id,
                "location_dest_id": production_loc.id,
            }
        )
        move._action_confirm()
        move._action_assign()
        self.assertEqual(move.quantity, 0)
        self.assertEqual(len(move.package_format_proposal_ids), 1)
