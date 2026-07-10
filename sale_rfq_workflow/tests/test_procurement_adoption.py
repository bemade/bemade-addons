from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestProcurementAdoption(TransactionCase):
    """SO confirmation must adopt the wizard-generated supply RFQs instead of
    regenerating fresh RFQs from supplier-info pricing.

    Baseline behaviour being fixed: core ``_make_po_get_domain`` only matches
    draft POs, so a supply RFQ in state 'sent' (i.e. one that has been quoted
    by the vendor) was bypassed and a duplicate PO was created at confirm,
    without the vendor pricing or communication thread.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.buy_route = env.ref('purchase_stock.route_warehouse0_buy')
        # Deliver-in-1-step as deployed at the client: short stock flips the
        # delivery leg to MTO, chaining the SO procurement into the buy rule —
        # the exact path that regenerated RFQs.
        wh = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
        wh.delivery_route_id.rule_ids.filtered(
            lambda r: r.action == 'pull').procure_method = 'mts_else_mto'

        cls.customer = env['res.partner'].create({
            'name': 'Adoption Customer', 'is_company': True,
        })
        cls.vendor_a = env['res.partner'].create({
            'name': 'Adoption Vendor A', 'is_company': True,
        })
        cls.vendor_b = env['res.partner'].create({
            'name': 'Adoption Vendor B', 'is_company': True,
        })

        cls.product_a = cls._make_product('Adopt Product A', cls.vendor_a, seller_price=10.0)
        cls.product_b = cls._make_product('Adopt Product B', cls.vendor_b, seller_price=20.0)

    @classmethod
    def _make_product(cls, name, vendor, seller_price):
        return cls.env['product.product'].create({
            'name': name,
            'type': 'consu',
            'is_storable': True,
            'route_ids': [Command.link(cls.buy_route.id)],
            'seller_ids': [Command.create({
                'partner_id': vendor.id,
                'price': seller_price,
                'min_qty': 0,
                'delay': 0,
            })],
        })

    def _make_so(self, lines):
        return self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': qty})
                for product, qty in lines
            ],
        })

    def _generate_rfqs(self, so):
        action = so.action_generate_supply_rfqs()
        wizard = self.env[action['res_model']].with_context(action['context']).create({})
        wizard.action_confirm()
        return so.supply_rfq_ids

    def _pos_for(self, so):
        return self.env['purchase.order'].search([
            ('origin', 'like', so.name), ('state', '!=', 'cancel'),
        ])

    def test_baseline_without_supply_rfq_creates_po(self):
        """Guard: SOs without supply RFQs keep the standard flow — confirming
        creates a fresh RFQ from supplier info."""
        so = self._make_so([(self.product_a, 3)])
        so.action_confirm()
        pos = self._pos_for(so)
        self.assertEqual(len(pos), 1)
        self.assertFalse(pos.supply_sale_order_id)
        self.assertEqual(pos.partner_id, self.vendor_a)

    def test_sent_rfq_adopted_on_confirm(self):
        """A quoted ('sent') supply RFQ is adopted: no duplicate PO, quantity
        not doubled, quoted price preserved."""
        so = self._make_so([(self.product_a, 3)])
        rfq = self._generate_rfqs(so)
        self.assertEqual(len(rfq), 1)
        line = rfq.order_line
        self.assertEqual(line.sale_line_id, so.order_line)

        # Vendor quoted: price applied, RFQ marked sent.
        line.price_unit = 9.5
        rfq.write({'state': 'sent'})

        so.action_confirm()

        pos = self._pos_for(so)
        self.assertEqual(pos, rfq, "confirm must not create a duplicate PO")
        self.assertEqual(line.product_qty, 3, "quantity must not be doubled")
        self.assertEqual(line.price_unit, 9.5, "quoted price must survive adoption")

    def test_draft_rfq_adopted_on_confirm(self):
        so = self._make_so([(self.product_a, 2)])
        rfq = self._generate_rfqs(so)
        so.action_confirm()
        self.assertEqual(self._pos_for(so), rfq)
        self.assertEqual(rfq.order_line.product_qty, 2)

    def test_confirmed_rfq_not_duplicated(self):
        """A supply RFQ already confirmed to the vendor must not spawn an
        orphan duplicate at SO confirmation."""
        so = self._make_so([(self.product_a, 4)])
        rfq = self._generate_rfqs(so)
        rfq.order_line.price_unit = 9.0
        rfq.button_confirm()
        self.assertEqual(rfq.state, 'purchase')

        so.action_confirm()

        pos = self._pos_for(so)
        self.assertEqual(pos, rfq)
        self.assertEqual(rfq.order_line.product_qty, 4)
        self.assertEqual(rfq.order_line.price_unit, 9.0)

    def test_vendor_grouping_preserved(self):
        """Two vendors → each SO line adopts its own RFQ; the human grouping
        wins over automatic seller selection."""
        so = self._make_so([(self.product_a, 1), (self.product_b, 2)])
        rfqs = self._generate_rfqs(so)
        self.assertEqual(len(rfqs), 2)
        rfqs.write({'state': 'sent'})

        so.action_confirm()

        pos = self._pos_for(so)
        self.assertEqual(set(pos.ids), set(rfqs.ids))
        by_vendor = {po.partner_id: po for po in pos}
        self.assertEqual(by_vendor[self.vendor_a].order_line.product_id, self.product_a)
        self.assertEqual(by_vendor[self.vendor_b].order_line.product_id, self.product_b)

    def test_qty_increase_procures_delta(self):
        """Increasing the SO quantity after confirmation raises the adopted
        RFQ line to the new demand (not demand + old quantity)."""
        so = self._make_so([(self.product_a, 3)])
        rfq = self._generate_rfqs(so)
        rfq.order_line.price_unit = 9.5
        rfq.write({'state': 'sent'})
        so.action_confirm()
        self.assertEqual(rfq.order_line.product_qty, 3)

        so.order_line.product_uom_qty = 5

        self.assertEqual(self._pos_for(so), rfq)
        self.assertEqual(rfq.order_line.product_qty, 5,
                         "line must track the SO demand after a qty increase")
        self.assertEqual(rfq.order_line.price_unit, 9.5)

    def test_unquoted_zero_price_line_gets_seller_price(self):
        """An RFQ line still at 0.0 (never quoted) takes the supplier-info
        price on adoption rather than keeping a meaningless zero."""
        so = self._make_so([(self.product_a, 2)])
        rfq = self._generate_rfqs(so)
        self.assertEqual(rfq.order_line.price_unit, 0.0)

        so.action_confirm()

        self.assertEqual(self._pos_for(so), rfq)
        self.assertEqual(rfq.order_line.price_unit, 10.0)

    def test_new_so_line_after_generation(self):
        """A product added to the SO after RFQ generation has no supply line —
        it must still be procured (standard flow), without disturbing the
        adopted RFQ."""
        so = self._make_so([(self.product_a, 1)])
        rfq = self._generate_rfqs(so)
        rfq.order_line.price_unit = 9.5
        rfq.write({'state': 'sent'})

        so.write({'order_line': [Command.create({
            'product_id': self.product_b.id, 'product_uom_qty': 1,
        })]})
        so.action_confirm()

        pos = self._pos_for(so)
        self.assertIn(rfq, pos)
        self.assertEqual(rfq.order_line.product_qty, 1)
        other = pos - rfq
        self.assertEqual(other.partner_id, self.vendor_b)
