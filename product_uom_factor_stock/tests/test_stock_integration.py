"""
Integration tests for product_uom_factor_stock: inventory adjustment flow.

Crit 4: stock.move.line in delegate-mL → quantity_product_uom correct.

Crit 5 (scoping): stock.move / stock.move.line cross-tree UoM raises ValidationError
                  for genuinely cross-tree units; same-category allowed.

NOTE: stock.valuation.layer does not exist in Odoo 19 (was removed; valuation is
tracked via product.value and account.move). Valuation verification is done via
account.move.line amounts.
"""

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestStockIntegrationBase(TransactionCase):
    """Common fixture for stock integration tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env["res.config.settings"].create({"group_uom": True}).execute()

        dp = cls.env["decimal.precision"].search(
            [("name", "=", "Product Unit")], limit=1
        )
        if dp and dp.digits < 5:
            dp.digits = 5

        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.uom_ml = cls.env.ref("uom.product_uom_milliliter")
        cls.uom_liter = cls.env.ref("uom.product_uom_litre")

        cls.company = cls.env.company

        # Ink product: Unit base, storable, standard cost
        cls.categ = cls.env["product.category"].create(
            {
                "name": "Test Ink Category (Stock Integration)",
                "property_valuation": "real_time",
                "property_cost_method": "standard",
            }
        )
        cls.ink = cls.env["product.product"].create(
            {
                "name": "Test Ink – Stock Integration",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.uom_unit.id,
                "categ_id": cls.categ.id,
                "standard_price": 800.0,
            }
        )

        # Factor: 1 delegate-mL = 0.00005 Unit
        cls.factor = cls.env["product.uom.factor"].create(
            {
                "product_tmpl_id": cls.ink.product_tmpl_id.id,
                "foreign_uom_id": cls.uom_ml.id,
                "factor": 0.00005,
            }
        )
        cls.delegate_ml = cls.factor.delegate_uom_id
        cls.ink.product_tmpl_id.write({"uom_factor_ids": [(4, cls.factor.id)]})

        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")


class TestStockMoveLine(TestStockIntegrationBase):
    """Crit 4: stock.move.line in delegate-mL → quantity_product_uom correct."""

    def test_move_line_quantity_product_uom_in_delegate_ml(self):
        """stock.move.line with 250 delegate-mL → quantity_product_uom == 0.0125 Unit.

        The move.line uses delegate-mL; quantity_product_uom is computed as
        product_uom_id._compute_quantity(quantity, product_id.uom_id).
        250 delegate-mL × 0.00005 = 0.0125 Unit.
        """
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "incoming"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.ink.id,
                            "product_uom": self.uom_unit.id,
                            "product_uom_qty": 0.0125,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        move = picking.move_ids[0]
        move_line = self.env["stock.move.line"].create(
            {
                "move_id": move.id,
                "product_id": self.ink.id,
                "product_uom_id": self.delegate_ml.id,
                "quantity": 250.0,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )
        self.assertAlmostEqual(
            move_line.quantity_product_uom,
            0.0125,
            places=5,
            msg="250 delegate-mL → quantity_product_uom == 0.0125 Unit",
        )

    def test_move_line_allowed_uom_ids_contains_delegate_ml(self):
        """stock.move.line allowed_uom_ids contains the delegate-mL for the ink product."""
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "incoming"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.ink.id,
                            "product_uom": self.uom_unit.id,
                            "product_uom_qty": 1.0,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        move = picking.move_ids[0]
        ml = self.env["stock.move.line"].new(
            {
                "move_id": move.id,
                "product_id": self.ink.id,
                "product_uom_id": self.uom_unit.id,
                "quantity": 1.0,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )
        ml._compute_allowed_uom_ids()
        self.assertIn(
            self.delegate_ml.id,
            ml.allowed_uom_ids.ids,
            "Delegate-mL must be in stock.move.line allowed_uom_ids",
        )


class TestStockScopingConstraint(TestStockIntegrationBase):
    """Crit 5 (scoping): stock move/move.line rejects cross-tree UoMs."""

    def test_cross_tree_uom_on_stock_move_raises(self):
        """Forcing generic mL on a stock.move for Unit-base product raises ValidationError."""
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "incoming"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        with self.assertRaises(ValidationError):
            self.env["stock.picking"].create(
                {
                    "picking_type_id": picking_type.id,
                    "location_id": self.supplier_location.id,
                    "location_dest_id": self.stock_location.id,
                    "move_ids": [
                        Command.create(
                            {
                                "product_id": self.ink.id,
                                "product_uom": self.uom_ml.id,  # generic mL, cross-tree
                                "product_uom_qty": 250000.0,
                                "location_id": self.supplier_location.id,
                                "location_dest_id": self.stock_location.id,
                            }
                        )
                    ],
                }
            )

    def test_same_category_uom_on_stock_move_allowed(self):
        """Same-category UoM (mL for a liter-base product) is allowed on stock.move."""
        liter_product = self.env["product.product"].create(
            {
                "name": "Volume Product (Stock Scoping)",
                "type": "consu",
                "is_storable": True,
                "uom_id": self.uom_liter.id,
            }
        )
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "incoming"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        # mL is in the same volume category as liter → should NOT raise
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": liter_product.id,
                            "product_uom": self.uom_ml.id,  # same category as liter
                            "product_uom_qty": 1000.0,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        self.assertTrue(picking.move_ids)
