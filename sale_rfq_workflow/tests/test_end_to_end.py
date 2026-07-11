from odoo.tests import TransactionCase, tagged
from odoo.tools import float_compare


@tagged("-at_install", "post_install")
class TestSupplyProcurementAdoption(TransactionCase):
    """End-to-end repro of the SO -> supply-RFQ -> confirm cycle.

    The live bug (S00254): confirming a Sales Order whose demand is already
    covered by a wizard-generated supply RFQ triggers the core buy rule again,
    which creates a *duplicate* Purchase Order instead of adopting the RFQ the
    buyer already prepared (and priced via the quote analyzer).

    These tests pin the intended behaviour:
      * confirming the SO must NOT create a second RFQ for the same vendor,
      * the already-linked RFQ line keeps its analyzed price and quantity
        (no qty doubling, no price clobber),
      * increasing the SO qty afterwards still procures only the delta.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company

        # MTO ("Replenish on Order") is archived by default — activate it so
        # confirming the SO chains a buy procurement, exactly like production.
        cls.route_buy = env.ref("purchase_stock.route_warehouse0_buy")
        cls.route_mto = env.ref("stock.route_warehouse0_mto")
        cls.route_mto.active = True

        cls.customer = env["res.partner"].create({
            "name": "Adoption Customer",
            "is_company": True,
        })
        cls.vendor = env["res.partner"].create({
            "name": "Adoption Vendor",
            "is_company": True,
        })
        cls.uom_unit = env.ref("uom.product_uom_unit")

        cls.product = env["product.product"].create({
            "name": "MTO Widget",
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.uom_unit.id,
            "list_price": 20.0,
            "seller_ids": [(0, 0, {
                "partner_id": cls.vendor.id,
                "price": 10.0,
                "product_uom_id": cls.uom_unit.id,
                "min_qty": 0.0,
            })],
            "route_ids": [(6, 0, [cls.route_buy.id, cls.route_mto.id])],
        })

    def _make_so(self, qty=5.0):
        so = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": qty,
            })],
        })
        return so

    def _generate_rfq(self, so):
        """Drive the wizard end-to-end and return the created RFQ."""
        action = so.action_generate_supply_rfqs()
        Wizard = self.env[action["res_model"]].with_context(action["context"])
        wizard = Wizard.create({})
        # product already has a seller -> wizard jumps straight to review.
        wizard.action_confirm()
        self.assertEqual(len(so.supply_rfq_ids), 1)
        return so.supply_rfq_ids

    def _pos_for_vendor(self):
        return self.env["purchase.order"].search([
            ("partner_id", "=", self.vendor.id),
        ])

    def test_confirm_so_adopts_draft_rfq_no_duplicate(self):
        so = self._make_so(qty=5.0)
        rfq = self._generate_rfq(so)
        # Simulate the analyzer having applied a negotiated price.
        rfq.order_line.price_unit = 12.0

        so.action_confirm()

        pos = self._pos_for_vendor()
        self.assertEqual(
            len(pos), 1,
            "Confirming the SO must adopt the existing supply RFQ, not create "
            "a duplicate PO. Found: %s" % pos.mapped("name"),
        )
        self.assertEqual(rfq.order_line.product_qty, 5.0,
                         "Adopted RFQ line quantity must not be doubled.")
        self.assertEqual(rfq.order_line.price_unit, 12.0,
                         "Adopted RFQ line must keep its analyzed price.")
        # The demand move must be threaded onto the adopted RFQ line so that
        # confirming/receiving the RFQ feeds the SO delivery.
        self.assertTrue(
            rfq.order_line.move_dest_ids,
            "Adopted RFQ line must carry the SO delivery as its demand move.",
        )
        rfq.button_confirm()
        out_moves = so.order_line.move_ids.filtered(
            lambda m: m.location_dest_id.usage == "customer")
        self.assertTrue(
            rfq.order_line.move_ids & out_moves.move_orig_ids,
            "Confirming the adopted RFQ must create a receipt that feeds the "
            "SO delivery.",
        )

    def test_confirm_so_adopts_sent_rfq_no_duplicate(self):
        so = self._make_so(qty=5.0)
        rfq = self._generate_rfq(so)
        rfq.order_line.price_unit = 12.0
        # Buyer emailed the RFQ to the vendor -> state 'sent'. Core's
        # _make_po_get_domain matches state='draft' only, so this is the
        # case that most reliably duplicates in production.
        rfq.write({"state": "sent"})

        so.action_confirm()

        pos = self._pos_for_vendor()
        self.assertEqual(
            len(pos), 1,
            "A quoted ('sent') supply RFQ must still be adopted. Found: %s"
            % pos.mapped("name"),
        )
        self.assertEqual(rfq.order_line.product_qty, 5.0)
        self.assertEqual(rfq.order_line.price_unit, 12.0)

    def test_confirmed_rfq_incoming_move_satisfies_demand(self):
        so = self._make_so(qty=5.0)
        rfq = self._generate_rfq(so)
        rfq.order_line.price_unit = 12.0
        rfq.button_confirm()  # -> state 'purchase', incoming moves created

        so.action_confirm()

        pos = self._pos_for_vendor()
        self.assertEqual(
            len(pos), 1,
            "A confirmed supply RFQ's incoming moves must satisfy the SO "
            "demand — no new RFQ. Found: %s" % pos.mapped("name"),
        )
        # The demand chain must be real, not merely count-suppressed: the SO's
        # outgoing delivery move has to trace back to the RFQ's incoming move.
        out_moves = so.order_line.move_ids.filtered(
            lambda m: m.location_dest_id.usage == "customer")
        rfq_in_moves = rfq.order_line.move_ids.filtered(
            lambda m: m.location_id.usage == "supplier")
        self.assertTrue(rfq_in_moves, "Confirmed RFQ should have an incoming move.")
        self.assertTrue(
            out_moves.move_orig_ids & rfq_in_moves,
            "The SO delivery move must be fed by the confirmed RFQ's receipt "
            "(move_orig_ids chain), otherwise the demand is orphaned.",
        )

    def test_delta_quantity_still_procured(self):
        so = self._make_so(qty=5.0)
        rfq = self._generate_rfq(so)
        rfq.order_line.price_unit = 12.0
        so.action_confirm()

        # Nothing extra yet.
        self.assertEqual(len(self._pos_for_vendor()), 1)

        # Increase SO demand by 3 -> the extra demand must be procured.
        so.order_line.product_uom_qty = 8.0

        total_qty = sum(self._pos_for_vendor().order_line.mapped("product_qty"))
        self.assertEqual(
            float_compare(total_qty, 8.0, precision_digits=2), 0,
            "After raising SO qty to 8, total ordered qty across supply "
            "RFQ(s) must equal 8 (delta of 3 procured). Got %s" % total_qty,
        )
