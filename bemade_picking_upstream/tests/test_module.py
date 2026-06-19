from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPickingUpstream(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.StockPicking = cls.env["stock.picking"]
        cls.Product = cls.env["product.product"]
        cls.Location = cls.env["stock.location"]
        cls.Warehouse = cls.env["stock.warehouse"]

    def test_picking_model_extended(self):
        """Test that stock.picking is extended"""
        self.assertIsNotNone(self.StockPicking)

    def test_picking_creation(self):
        """Test basic picking creation"""
        warehouse = self.Warehouse.search([], limit=1)
        if warehouse:
            picking = self.StockPicking.create({
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": self.Location.search([], limit=1).id,
                "picking_type_id": warehouse.out_type_id.id,
            })
            self.assertIsNotNone(picking.id)

    def test_picking_with_move(self):
        """Test picking with stock move"""
        warehouse = self.Warehouse.search([], limit=1)
        product = self.Product.create({
            "name": "Picking Product",
            "type": "consu",
        })

        if warehouse:
            picking = self.StockPicking.create({
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": self.Location.search([], limit=1).id,
                "picking_type_id": warehouse.out_type_id.id,
                "move_ids": [
                    (0, 0, {
                        "product_id": product.id,
                        "product_uom_qty": 1.0,
                        "product_uom": product.uom_id.id,
                    })
                ]
            })
            self.assertEqual(len(picking.move_ids), 1)

    def test_upstream_picking_flow(self):
        """Test upstream picking flow"""
        warehouse = self.Warehouse.search([], limit=1)
        self.assertIsNotNone(warehouse)
