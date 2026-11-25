# -*- coding: utf-8 -*-
import re

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReportTrailingZeros(TransactionCase):
    """Fractional quantities print without trailing zeros (task 3072, round 2).

    Acceptance:
      - AC#5: a sale line at 0.1 prints "0.1" on the quotation/order PDF,
        not "0.100" (the UoM precision padding).
      - AC#6: a purchase line at 0.1 prints "0.1" on both the RFQ and the
        purchase order PDF.
      - AC#7: a fraction that needs every decimal (6.25) keeps them all.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create({
            "name": "Chem 3072", "type": "consu",
        })
        partner = cls.env["res.partner"].create({"name": "Partner 3072"})
        cls.sale = cls.env["sale.order"].create({
            "partner_id": partner.id,
            "order_line": [
                (0, 0, {"product_id": cls.product.id, "product_uom_qty": 0.1}),
                (0, 0, {"product_id": cls.product.id, "product_uom_qty": 6.25}),
            ],
        })
        cls.purchase = cls.env["purchase.order"].create({
            "partner_id": partner.id,
            "order_line": [
                (0, 0, {"product_id": cls.product.id, "product_qty": 0.1,
                        "price_unit": 1.0}),
                (0, 0, {"product_id": cls.product.id, "product_qty": 6.25,
                        "price_unit": 1.0}),
            ],
        })

    def _cells(self, html, name):
        html = html.decode() if isinstance(html, bytes) else html
        cells = re.findall(
            r'<td[^>]*name="%s"[^>]*>(.*?)</td>' % name, html, re.DOTALL
        )
        return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                for c in cells]

    def _assert(self, cells, label):
        self.assertTrue(cells, "%s: no quantity cells rendered" % label)
        self.assertTrue(any(c.startswith("0.1 ") or c == "0.1" for c in cells),
                        "%s: expected '0.1', got %r" % (label, cells))
        self.assertFalse(any("0.100" in c for c in cells),
                         "%s: trailing zeros still printed: %r" % (label, cells))
        self.assertTrue(any(c.startswith("6.25") for c in cells),
                        "%s: expected '6.25', got %r" % (label, cells))

    def test_sale_report(self):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "sale.report_saleorder", self.sale.ids)
        self._assert(self._cells(html, "td_product_quantity"), "Sale order")

    def test_purchase_order_report(self):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "purchase.report_purchaseorder", self.purchase.ids)
        self._assert(self._cells(html, "td_quantity"), "Purchase order")

    def test_rfq_report(self):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "purchase.report_purchasequotation", self.purchase.ids)
        self._assert(self._cells(html, "td_quantity"), "RFQ")
