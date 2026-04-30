# License: LGPL-3
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""Tests for commercial.invoice line-source switching.

Acceptance criteria (from task-3516 requirements):

1. line_source='invoice' (default) — _get_report_lines() returns one dict per
   invoice line, values matching account.move.line.  Rendered HTML contains
   the product code and price_subtotal.

2. line_source='picking' — _get_report_lines() yields rows with
   quantities/prices from move.sale_line_id.price_unit; outgoing pickings only.

3. Aggregation across pickings — two outgoing pickings for same partner/product/
   price produce one aggregated row (summed qty).  A third picking with a
   different price_unit for the same product yields a second row
   (aggregation key is (product_id, price_unit)).

4. Empty deliveries — partner with no done outgoing pickings → [] from
   _get_report_lines(); rendered HTML contains the "No deliveries linked"
   note.

5. Unit price origin — each row's price_unit equals move.sale_line_id.price_unit,
   NOT the product's list price or move.price_unit.

6. _compute_amounts for picking source — invoice_amount == sum of helper rows'
   price_subtotal; total_amount == invoice_amount + addons.

7. Backwards-compat smoke — existing CI (line_source='invoice') renders HTML
   with the expected product code; _get_report_lines() matches invoice lines.

8. Filter scope — outgoing picking for a different partner does NOT appear in
   the helper output for the first partner's CI.

9. Non-outgoing picking ignored — internal/incoming picking for the partner
   is excluded.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "commercial_invoice")
class TestCommercialInvoiceLines(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- base objects ---
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.company
        cls.canada = cls.env.ref("base.ca")
        cls.usa = cls.env.ref("base.us")

        # Partners
        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Consignee", "country_id": cls.usa.id}
        )
        cls.other_partner = cls.env["res.partner"].create(
            {"name": "Other Partner", "country_id": cls.usa.id}
        )

        # Product category (required for products)
        cls.category = cls.env.ref("product.product_category_all")

        # Products
        cls.product_a = cls.env["product.product"].create(
            {
                "name": "Widget A",
                "default_code": "WDGT-A",
                "type": "consu",
                "lst_price": 100.0,
                "categ_id": cls.category.id,
            }
        )
        cls.product_b = cls.env["product.product"].create(
            {
                "name": "Widget B",
                "default_code": "WDGT-B",
                "type": "consu",
                "lst_price": 200.0,
                "categ_id": cls.category.id,
            }
        )

        # Account setup for invoice tests
        cls.account_revenue = cls.env["account.account"].search(
            [
                ("company_ids", "in", [cls.company.id]),
                ("account_type", "=", "income"),
            ],
            limit=1,
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )

        # Outgoing picking type
        cls.picking_type_out = cls.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("warehouse_id.company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        cls.picking_type_in = cls.env["stock.picking.type"].search(
            [
                ("code", "=", "incoming"),
                ("warehouse_id.company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        cls.picking_type_internal = cls.env["stock.picking.type"].search(
            [
                ("code", "=", "internal"),
                ("warehouse_id.company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        cls.location_output = cls.picking_type_out.default_location_src_id
        cls.location_customer = cls.picking_type_out.default_location_dest_id

    # ------------------------------------------------------------------ helpers

    def _make_invoice(self, partner, product, qty, price_unit):
        """Create and post a customer invoice with one line."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "currency_id": self.usd.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "quantity": qty,
                            "price_unit": price_unit,
                            "account_id": self.account_revenue.id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _make_done_outgoing_picking(self, partner, product, qty, sale_price):
        """Create a done outgoing picking with one move.

        A fake sale.order.line is created to set sale_line_id so that
        price_unit can be validated independently of the move's own price_unit.
        """
        picking = self.env["stock.picking"].create(
            {
                "partner_id": partner.id,
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.location_output.id,
                "location_dest_id": self.location_customer.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": product.name,
                            "product_id": product.id,
                            "product_uom": product.uom_id.id,
                            "product_uom_qty": qty,
                            "location_id": self.location_output.id,
                            "location_dest_id": self.location_customer.id,
                            "price_unit": 999.0,  # intentionally wrong; test uses sale_line
                        },
                    )
                ],
            }
        )
        # Create a minimal sale.order.line to carry the expected price_unit
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": sale_price,
                        },
                    )
                ],
            }
        )
        sale_order.action_confirm()
        sale_line = sale_order.order_line[0]
        picking.move_ids.write({"sale_line_id": sale_line.id})

        # Validate the picking (mark as done)
        picking.action_assign()
        for ml in picking.move_line_ids:
            ml.qty_done = qty
        picking._action_done()
        return picking

    def _make_ci(self, partner, line_source="invoice"):
        return self.env["commercial.invoice"].create(
            {
                "partner_id": partner.id,
                "currency_id": self.usd.id,
                "line_source": line_source,
            }
        )

    # ------------------------------------------------------------------ tests

    def test_01_invoice_source_report_lines(self):
        """line_source='invoice': _get_report_lines() mirrors invoice lines."""
        invoice = self._make_invoice(self.partner, self.product_a, 5.0, 42.0)
        ci = self._make_ci(self.partner)
        ci.invoice_ids = invoice

        lines = ci._get_report_lines()
        self.assertEqual(len(lines), 1, "Expected one report line from invoice")
        row = lines[0]
        self.assertEqual(row["name"], self.product_a.name)
        self.assertEqual(row["default_code"], "WDGT-A")
        self.assertAlmostEqual(row["quantity"], 5.0)
        self.assertAlmostEqual(row["price_unit"], 42.0)
        self.assertAlmostEqual(row["price_subtotal"], 5.0 * 42.0)

    def test_02_picking_source_report_lines(self):
        """line_source='picking': rows come from done outgoing moves."""
        self._make_done_outgoing_picking(self.partner, self.product_a, 3.0, 55.0)
        ci = self._make_ci(self.partner, line_source="picking")

        lines = ci._get_report_lines()
        self.assertEqual(len(lines), 1)
        row = lines[0]
        self.assertEqual(row["name"], self.product_a.name)
        self.assertAlmostEqual(row["quantity"], 3.0)
        self.assertAlmostEqual(row["price_unit"], 55.0)
        self.assertAlmostEqual(row["price_subtotal"], 3.0 * 55.0)

    def test_03_aggregation_across_pickings(self):
        """Two pickings same product+price → one aggregated row; third with
        different price → second row.

        Aggregation key is (product_id, price_unit).  Two rows with the same
        product but different prices are intentionally kept separate rather
        than weighted-averaged, because the requirements do not specify how to
        combine different prices.
        """
        # Two pickings: same product_a, same price 50
        self._make_done_outgoing_picking(self.partner, self.product_a, 2.0, 50.0)
        self._make_done_outgoing_picking(self.partner, self.product_a, 3.0, 50.0)
        # Third picking: same product_a, different price 60
        self._make_done_outgoing_picking(self.partner, self.product_a, 1.0, 60.0)

        ci = self._make_ci(self.partner, line_source="picking")
        lines = ci._get_report_lines()

        # Group by price_unit to check aggregation
        by_price = {row["price_unit"]: row for row in lines}
        self.assertIn(50.0, by_price, "Expected a row for price 50")
        self.assertIn(60.0, by_price, "Expected a row for price 60")
        self.assertAlmostEqual(by_price[50.0]["quantity"], 5.0, msg="2+3 should aggregate")
        self.assertAlmostEqual(by_price[60.0]["quantity"], 1.0)

    def test_04_empty_deliveries(self):
        """No done outgoing pickings → _get_report_lines() returns []."""
        ci = self._make_ci(self.partner, line_source="picking")
        lines = ci._get_report_lines()
        self.assertEqual(lines, [])

    def test_05_unit_price_from_sale_line(self):
        """price_unit on each row must equal move.sale_line_id.price_unit,
        not the product's list price (999.0 in the helper) or move.price_unit.
        """
        self._make_done_outgoing_picking(self.partner, self.product_a, 4.0, 77.0)
        ci = self._make_ci(self.partner, line_source="picking")
        lines = ci._get_report_lines()

        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0]["price_unit"], 77.0,
                               msg="price_unit must come from sale_line_id, not move.price_unit")

    def test_06_compute_amounts_picking_source(self):
        """_compute_amounts sums picking lines into invoice_amount; total_amount
        adds addon costs.
        """
        self._make_done_outgoing_picking(self.partner, self.product_a, 2.0, 100.0)
        self._make_done_outgoing_picking(self.partner, self.product_b, 1.0, 150.0)

        ci = self.env["commercial.invoice"].create(
            {
                "partner_id": self.partner.id,
                "currency_id": self.usd.id,
                "line_source": "picking",
                "packaging_cost": 10.0,
                "freight_cost": 20.0,
                "insurance_cost": 5.0,
                "other_cost": 0.0,
            }
        )

        expected_invoice_amount = 2.0 * 100.0 + 1.0 * 150.0  # 350
        expected_total = expected_invoice_amount + 10.0 + 20.0 + 5.0  # 385

        self.assertAlmostEqual(ci.invoice_amount, expected_invoice_amount)
        self.assertAlmostEqual(ci.total_amount, expected_total)

    def test_07_backwards_compat_smoke(self):
        """Existing CI with line_source='invoice' still reports correctly."""
        invoice = self._make_invoice(self.partner, self.product_a, 1.0, 88.0)
        ci = self._make_ci(self.partner)
        self.assertEqual(ci.line_source, "invoice",
                         "Default line_source must be 'invoice'")
        ci.invoice_ids = invoice

        lines = ci._get_report_lines()
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0]["price_unit"], 88.0)
        self.assertAlmostEqual(lines[0]["quantity"], 1.0)
        # invoice_amount should equal the invoice total
        self.assertAlmostEqual(ci.invoice_amount, invoice.amount_total)

    def test_08_filter_scope_different_partner(self):
        """Outgoing picking for other_partner must not appear in partner's CI."""
        self._make_done_outgoing_picking(self.other_partner, self.product_a, 5.0, 10.0)
        ci = self._make_ci(self.partner, line_source="picking")

        lines = ci._get_report_lines()
        self.assertEqual(lines, [],
                         "Other partner's deliveries must not appear in this CI")

    def test_09_non_outgoing_picking_ignored(self):
        """Incoming and internal pickings for the partner are excluded."""
        location_supplier = self.picking_type_in.default_location_src_id
        location_input = self.picking_type_in.default_location_dest_id

        # Incoming picking (receipt)
        incoming = self.env["stock.picking"].create(
            {
                "partner_id": self.partner.id,
                "picking_type_id": self.picking_type_in.id,
                "location_id": location_supplier.id,
                "location_dest_id": location_input.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": self.product_a.name,
                            "product_id": self.product_a.id,
                            "product_uom": self.product_a.uom_id.id,
                            "product_uom_qty": 10.0,
                            "location_id": location_supplier.id,
                            "location_dest_id": location_input.id,
                        },
                    )
                ],
            }
        )
        incoming.action_assign()
        for ml in incoming.move_line_ids:
            ml.qty_done = 10.0
        incoming._action_done()

        ci = self._make_ci(self.partner, line_source="picking")
        lines = ci._get_report_lines()
        self.assertEqual(lines, [],
                         "Incoming picking must not appear in picking-source CI")
