# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Synthetic fixture: « Resin X » stocked in a cubic-foot base unit, sold and
bought in three formats: bag (1 ft³), drum (5 ft³) and bulk bag (42 ft³)."""

from odoo.fields import Command
from odoo.tests import TransactionCase


class PackageFormatCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        env = cls.env
        cls.company = env.company
        cls.warehouse = env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.stock = cls.warehouse.lot_stock_id
        cls.supplier_loc = env.ref("stock.stock_location_suppliers")
        cls.customer_loc = env.ref("stock.stock_location_customers")
        # Packages and lots must be visible to the test user (views, Form).
        env.user.group_ids = [
            Command.link(env.ref("stock.group_tracking_lot").id),
            Command.link(env.ref("stock.group_production_lot").id),
            Command.link(env.ref("uom.group_uom").id),
            Command.link(env.ref("stock.group_stock_manager").id),
        ]

        Uom = env["uom.uom"]
        cls.uom_ft3 = Uom.create({"name": "ft3 (test)", "relative_factor": 1.0})
        PackType = env["stock.package.type"]
        cls.type_bag = PackType.create({"name": "Bag 1 ft3 (test)"})
        cls.type_drum = PackType.create({"name": "Drum 5 ft3 (test)"})
        cls.type_bulk = PackType.create({"name": "Bulk bag 42 ft3 (test)"})
        cls.uom_bag = Uom.create(
            {
                "name": "BAG (test)",
                "relative_uom_id": cls.uom_ft3.id,
                "relative_factor": 1.0,
                "package_type_id": cls.type_bag.id,
            }
        )
        cls.uom_drum = Uom.create(
            {
                "name": "DRUM (test)",
                "relative_uom_id": cls.uom_ft3.id,
                "relative_factor": 5.0,
                "package_type_id": cls.type_drum.id,
            }
        )
        cls.uom_bulk = Uom.create(
            {
                "name": "BULK (test)",
                "relative_uom_id": cls.uom_ft3.id,
                "relative_factor": 42.0,
                "package_type_id": cls.type_bulk.id,
            }
        )
        cls.categ = env["product.category"].create({"name": "Resins (test)"})
        cls.vendor = env["res.partner"].create({"name": "Resin Vendor (test)"})
        cls.customer = env["res.partner"].create({"name": "Water Customer (test)"})
        cls.buy_route = env.ref("purchase_stock.route_warehouse0_buy")
        cls.product = env["product.product"].create(
            {
                "name": "Resin X",
                "is_storable": True,
                "tracking": "lot",
                "categ_id": cls.categ.id,
                "uom_id": cls.uom_ft3.id,
                "uom_ids": [
                    Command.set([cls.uom_bag.id, cls.uom_drum.id, cls.uom_bulk.id])
                ],
                "route_ids": [Command.set(cls.buy_route.ids)],
                "seller_ids": [
                    Command.create(
                        {
                            "partner_id": cls.vendor.id,
                            "price": 100.0,
                            "product_uom_id": cls.uom_ft3.id,
                        }
                    )
                ],
            }
        )
        cls.categ.package_rule = True
        # An unflagged twin, to prove standard behaviour is untouched.
        cls.plain_product = env["product.product"].create(
            {
                "name": "Plain Media Y",
                "is_storable": True,
                "uom_id": cls.uom_ft3.id,
                "uom_ids": [Command.set([cls.uom_bag.id, cls.uom_drum.id])],
            }
        )
        cls.opener = env["res.users"].create(
            {
                "name": "Package Opener (test)",
                "login": "pkg_opener_test",
                "group_ids": [
                    Command.set(
                        [
                            env.ref("stock.group_stock_user").id,
                            env.ref("stock_package_format.group_package_open").id,
                        ]
                    )
                ],
            }
        )
        cls.stock_user = env["res.users"].create(
            {
                "name": "Stock Clerk (test)",
                "login": "pkg_clerk_test",
                "group_ids": [Command.set([env.ref("stock.group_stock_user").id])],
            }
        )

    # -- helpers ---------------------------------------------------------
    def _lot(self, name, product=None):
        product = product or self.product
        lot = self.env["stock.lot"].search(
            [("name", "=", name), ("product_id", "=", product.id)], limit=1
        )
        return lot or self.env["stock.lot"].create(
            {"name": name, "product_id": product.id, "company_id": self.company.id}
        )

    def _put_packages(self, uom, count, lot_name="L0", location=None, opened=False):
        """Put `count` packages of format `uom` (one lot) directly in stock."""
        location = location or self.stock
        lot = self._lot(lot_name)
        size = uom._compute_quantity(1, self.product.uom_id)
        packages = self.env["stock.package"]
        for _i in range(count):
            package = self.env["stock.package"].create(
                {"package_type_id": uom.package_type_id.id}
            )
            self.env["stock.quant"]._update_available_quantity(
                self.product, location, size, lot_id=lot, package_id=package
            )
            packages |= package
        if opened:
            packages.write({"is_opened": True})
        return packages

    def _put_loose(self, qty, lot_name=None, product=None, location=None):
        product = product or self.product
        lot = self._lot(lot_name, product) if lot_name else None
        self.env["stock.quant"]._update_available_quantity(
            product, location or self.stock, qty, lot_id=lot
        )

    def _receipt(self, qty, uom, product=None):
        product = product or self.product
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.in_type_id.id,
                "location_id": self.supplier_loc.id,
                "location_dest_id": self.stock.id,
                "partner_id": self.vendor.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "product_uom": uom.id,
                            "location_id": self.supplier_loc.id,
                            "location_dest_id": self.stock.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        return picking

    def _delivery(self, qty, uom, product=None, location=None):
        product = product or self.product
        location = location or self.stock
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": location.id,
                "location_dest_id": self.customer_loc.id,
                "partner_id": self.customer.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "product_uom": uom.id,
                            "location_id": location.id,
                            "location_dest_id": self.customer_loc.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        return picking

    def _run_pack_wizard(self, action, rows=None):
        """Fill the pack wizard opened by `action`. `rows` replaces the
        default rows: list of (format uom, package count, lot name)."""
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        if rows is not None:
            move = wizard.line_ids[:1].move_id
            wizard.line_ids.unlink()
            for uom, count, lot_name in rows:
                self.env["stock.package.format.pack.wizard.line"].create(
                    {
                        "wizard_id": wizard.id,
                        "move_id": move.id,
                        "format_uom_id": uom.id,
                        "package_count": count,
                        "lot_name": lot_name,
                    }
                )
        return wizard, wizard.action_confirm()

    def _free_qty(self, product=None, location=None):
        product = product or self.product
        return self.env["stock.quant"]._get_available_quantity(
            product, location or self.stock
        )
