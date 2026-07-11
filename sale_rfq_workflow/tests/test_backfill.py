from odoo.tests import TransactionCase, tagged

from odoo.addons.sale_rfq_workflow.hooks import _backfill_supply_sale_line


@tagged("-at_install", "post_install")
class TestBackfillHook(TransactionCase):
    """The post_init_hook backfills core sale_line_id from supply_so_line_id
    on in-flight supply RFQ lines so orders already in flight become adoptable
    without being re-created (e.g. after a monolith -> split upgrade)."""

    def _setup(self, state="draft"):
        env = self.env
        customer = env["res.partner"].create({
            "name": "Mig Customer", "is_company": True})
        vendor = env["res.partner"].create({
            "name": "Mig Vendor", "is_company": True})
        uom = env.ref("uom.product_uom_unit")
        product = env["product.product"].create({
            "name": "Mig Widget", "type": "consu", "uom_id": uom.id})
        so = env["sale.order"].create({
            "partner_id": customer.id,
            "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 2})],
        })
        po = env["purchase.order"].create({
            "partner_id": vendor.id,
            "supply_sale_order_id": so.id,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "name": product.name,
                "product_qty": 2,
                "product_uom_id": uom.id,
                "supply_so_line_id": so.order_line.id,
            })],
        })
        line = po.order_line
        # Simulate an "old" line that predates the sale_line_id linkage, and
        # force the order state at the DB level (the backfill filters on the
        # stored state column directly).
        env.cr.execute(
            "UPDATE purchase_order SET state = %s WHERE id = %s",
            (state, po.id),
        )
        env.cr.execute(
            "UPDATE purchase_order_line SET sale_line_id = NULL WHERE id = %s",
            (line.id,),
        )
        po.invalidate_recordset(["state"])
        line.invalidate_recordset(["sale_line_id"])
        self.assertFalse(line.sale_line_id)
        return so, line

    def test_backfill_sets_sale_line_id(self):
        so, line = self._setup()
        _backfill_supply_sale_line(self.env)
        line.invalidate_recordset(["sale_line_id"])
        self.assertEqual(
            line.sale_line_id, so.order_line,
            "Backfill must set sale_line_id from supply_so_line_id.",
        )

    def test_backfill_skips_done_orders(self):
        """A cancelled RFQ line is not an in-flight order — leave it alone."""
        so, line = self._setup(state="cancel")
        _backfill_supply_sale_line(self.env)
        line.invalidate_recordset(["sale_line_id"])
        self.assertFalse(
            line.sale_line_id,
            "Backfill must only touch draft/sent/purchase RFQ lines.",
        )
