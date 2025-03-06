from odoo.tests import TransactionCase, Form, tagged
from odoo.addons.sale.tests.common import TestSaleCommon
from odoo import Command


@tagged("-at_install", "post_install")
class TestSaleOrder(TestSaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        groups = [
            cls.env.ref('base.group_user').id,
            cls.env.ref('base.group_system').id,
            cls.env.ref('account.group_account_invoice').id,
            cls.env.ref('sales_team.group_sale_manager').id,
        ]
        cls.user = cls.env['res.users'].create({
            'partner_id': Partner.create({'name': 'user1'}).id,
            'login': 'test_user',
            'password': 'test_user',
            'groups_id': [Command.set(groups)]
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'default_code': 'TEST',
            'price': 10.0,
            'invoice_policy': 'order',
        })
        cls.sale_order = cls.env['sale.order'].with_user(cls.user).create({
            'partner_id': cls.partner_a.id,
        })
        so_form = Form(cls.sale_order)
        with so_form.order_line.new() as line:
            line.product_id = cls.product
            line.product_uom_qty = 2
        so_form.save()
        cls.sale_order.action_confirm()

    def test_invoice_wizard_does_not_set_so_responsible_as_invoice_follower(self):
        so = self.sale_order
        admin = self.env.ref('base.user_root')
        wiz = self.env['sale.advance.payment.inv'].with_user(admin).with_context({
            'active_ids': so.ids,
            'active_model': 'sale.order',
        }).create({})
        wiz.with_user(admin).create_invoices()
        invoice = so.invoice_ids[0]
        self.assertEqual(invoice.invoice_user_id, admin)
        self.assertFalse(self.user in invoice.message_follower_ids.mapped('partner_id').mapped('user_ids'))


