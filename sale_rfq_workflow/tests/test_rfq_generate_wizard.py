from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestRfqGenerateWizard(TransactionCase):
    """Coverage for the Generate Supply RFQs wizard.

    Particularly the path where a SO line product has no primary vendor and
    the user picks one in the wizard's first step. action_next has to
    create a product.supplierinfo for the (vendor, product) pair — and on
    Odoo 19, supplierinfo.product_uom_id is a required field, so the
    create call must populate it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.customer = env["res.partner"].create({
            "name": "Generate-RFQs Customer",
            "is_company": True,
        })
        cls.vendor = env["res.partner"].create({
            "name": "Generate-RFQs Vendor",
            "is_company": True,
        })

        cls.uom_unit = env.ref("uom.product_uom_unit")
        cls.uom_dozen = env.ref("uom.product_uom_dozen")

        # A consumable product with no seller_ids configured at all.
        cls.product_no_vendor = env["product.product"].create({
            "name": "Widget without vendor",
            "type": "consu",
            "uom_id": cls.uom_unit.id,
            "list_price": 10.0,
        })
        # A second product on a non-default UoM, also with no vendor — used
        # to confirm the wizard does not assume Units.
        cls.product_no_vendor_dozen = env["product.product"].create({
            "name": "Bundle without vendor",
            "type": "consu",
            "uom_id": cls.uom_dozen.id,
            "list_price": 12.0,
        })

        cls.so = env["sale.order"].create({
            "partner_id": cls.customer.id,
            "order_line": [
                (0, 0, {
                    "product_id": cls.product_no_vendor.id,
                    "product_uom_qty": 5,
                }),
                (0, 0, {
                    "product_id": cls.product_no_vendor_dozen.id,
                    "product_uom_qty": 2,
                }),
            ],
        })

    def _open_wizard(self):
        action = self.so.action_generate_supply_rfqs()
        Wizard = self.env[action["res_model"]].with_context(action["context"])
        return Wizard.create({})

    def test_action_next_creates_supplierinfo_with_uom(self):
        """Picking a vendor in step 1 and pressing Next should persist the
        choice as a product.supplierinfo with product_uom_id set."""
        wizard = self._open_wizard()

        # Both products lack a vendor — the wizard should surface them.
        prompted_tmpls = wizard.vendor_line_ids.mapped("product_tmpl_id")
        self.assertIn(self.product_no_vendor.product_tmpl_id, prompted_tmpls)
        self.assertIn(self.product_no_vendor_dozen.product_tmpl_id, prompted_tmpls)

        # Pick the same vendor on every line and advance.
        wizard.vendor_line_ids.write({"vendor_id": self.vendor.id})
        wizard.action_next()

        # One supplierinfo per (product_tmpl, vendor); product_uom_id must
        # come from the product (Units for one, Dozen for the other) — the
        # 19.0 NOT NULL constraint on supplierinfo.product_uom_id makes
        # this a regression-blocking assertion.
        supplierinfo = self.env["product.supplierinfo"].search([
            ("partner_id", "=", self.vendor.id),
            ("product_tmpl_id", "in", prompted_tmpls.ids),
        ])
        self.assertEqual(len(supplierinfo), 2)
        by_tmpl = {s.product_tmpl_id: s for s in supplierinfo}
        self.assertEqual(
            by_tmpl[self.product_no_vendor.product_tmpl_id].product_uom_id,
            self.uom_unit,
        )
        self.assertEqual(
            by_tmpl[self.product_no_vendor_dozen.product_tmpl_id].product_uom_id,
            self.uom_dozen,
        )

        # Wizard should have advanced into the review state.
        self.assertEqual(wizard.state, "review")
        self.assertTrue(wizard.group_line_ids)

        # action_confirm creates the actual RFQ; this is where the
        # purchase.order.line tax_ids rename (19.0: taxes_id -> tax_ids)
        # would otherwise blow up.
        wizard.action_confirm()
        rfqs = self.so.supply_rfq_ids
        self.assertEqual(len(rfqs), 1)
        rfq = rfqs[0]
        self.assertEqual(rfq.partner_id, self.vendor)
        self.assertEqual(
            set(rfq.order_line.mapped("product_id.product_tmpl_id.id")),
            set(prompted_tmpls.ids),
        )
        # Wizard-created RFQ lines must carry BOTH the bespoke and core links
        # so the procurement engine can adopt them on SO confirm.
        self.assertTrue(all(rfq.order_line.mapped("supply_so_line_id")))
        self.assertTrue(all(rfq.order_line.mapped("sale_line_id")))
        for pol in rfq.order_line:
            self.assertEqual(pol.supply_so_line_id, pol.sale_line_id)

    def test_view_supply_rfqs_action(self):
        """The smart-button action targets a single RFQ as a form and multiple
        RFQs as a filtered list; the count compute tracks the linked RFQs."""
        # Two products, two distinct vendors -> two RFQs.
        vendor2 = self.env["res.partner"].create({
            "name": "Second Vendor", "is_company": True})
        wizard = self._open_wizard()
        wizard.vendor_line_ids.filtered(
            lambda l: l.product_tmpl_id == self.product_no_vendor.product_tmpl_id
        ).vendor_id = self.vendor
        wizard.vendor_line_ids.filtered(
            lambda l: l.product_tmpl_id == self.product_no_vendor_dozen.product_tmpl_id
        ).vendor_id = vendor2
        wizard.action_next()
        wizard.action_confirm()

        self.assertEqual(self.so.supply_rfq_count, 2)
        multi = self.so.action_view_supply_rfqs()
        # Multiple RFQs -> a filtered list, not a specific record.
        self.assertFalse(multi.get("res_id"))
        self.assertNotEqual(multi.get("view_mode"), "form")
        self.assertEqual(multi["domain"], [("supply_sale_order_id", "=", self.so.id)])

        # Now a single-RFQ order opens straight to the form.
        so1 = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "order_line": [(0, 0, {
                "product_id": self.product_no_vendor.id,
                "product_uom_qty": 1})],
        })
        action = so1.action_generate_supply_rfqs()
        w = self.env[action["res_model"]].with_context(action["context"]).create({})
        w.vendor_line_ids.write({"vendor_id": self.vendor.id})
        w.action_next()
        w.action_confirm()
        self.assertEqual(so1.supply_rfq_count, 1)
        single = so1.action_view_supply_rfqs()
        self.assertEqual(single["res_id"], so1.supply_rfq_ids.id)
        self.assertEqual(single["view_mode"], "form")

    def test_action_next_skips_orphan_vendor_line(self):
        """Defensive: if a vendor_line ends up with no product_tmpl_id (the
        web client is known to drop readonly fields under some conditions
        despite force_save), the wizard must skip it instead of trying to
        create an orphan supplierinfo."""
        wizard = self._open_wizard()
        # Vendor every real line so action_next clears its missing-vendor guard.
        wizard.vendor_line_ids.write({"vendor_id": self.vendor.id})
        real_tmpl_ids = wizard.vendor_line_ids.mapped("product_tmpl_id").ids

        # Inject an orphan vendor_line — vendor selected, but
        # product_tmpl_id never made it back to the server.
        self.env["sale.rfq.generate.vendor.line"].create({
            "wizard_id": wizard.id,
            "vendor_id": self.vendor.id,
        })

        wizard.action_next()  # should not raise on the orphan

        # One supplierinfo per real line — none for the orphan.
        sis = self.env["product.supplierinfo"].search([
            ("partner_id", "=", self.vendor.id),
        ])
        self.assertEqual(set(sis.mapped("product_tmpl_id").ids), set(real_tmpl_ids))
        self.assertTrue(all(s.product_uom_id for s in sis))
