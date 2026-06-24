from lxml import etree

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCovPOCreateBillButton(TransactionCase):
    """The Sports Clinic vendor-PO workflow needs a one-click "Create Bill"
    on the purchase.order form.

    Odoo 19 removed the form-header "Create Bill" button (it now lives only in
    the Purchase Orders *list* header and expects the bill-matching flow). The
    therapists this module bills don't send invoices, so we restore a direct
    "Create Bill" button on the PO form that calls the stock
    ``action_create_invoice`` to generate an internal draft vendor bill.

    Acceptance criteria
    -------------------
    1. The purchase.order form view exposes a button bound to
       ``action_create_invoice``.
    2. A confirmed vendor PO whose lines use an "on ordered quantities" service
       product is billable (``invoice_status == 'to invoice'``) with **no goods
       receipt**, and ``action_create_invoice`` produces a single draft vendor
       bill linked back to the PO.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env['res.partner'].create({'name': 'Bill Button Therapist'})
        # Mirrors the module's vendor fee products: a service billed on ordered
        # quantities, so it is billable on confirmation without any receipt.
        cls.service = cls.env['product.product'].create({
            'name': 'Coverage Fee (Vendor)',
            'type': 'service',
            'purchase_method': 'purchase',
        })

    def test_form_has_create_bill_button(self):
        arch = self.env['purchase.order'].get_view(view_type='form')['arch']
        tree = etree.fromstring(arch)
        self.assertTrue(
            tree.xpath("//button[@name='action_create_invoice']"),
            "PO form view should expose a 'Create Bill' button "
            "(action_create_invoice) to restore the 18.0 workflow.",
        )

    def test_confirmed_po_bills_without_receipt(self):
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'order_line': [Command.create({
                'product_id': self.service.id,
                'name': 'Coverage',
                'product_qty': 2.0,
                'price_unit': 30.0,
            })],
        })
        po.button_confirm()

        self.assertEqual(po.order_line.qty_received, 0.0,
                         "service line should have no received qty")
        self.assertEqual(po.invoice_status, 'to invoice',
                         "an 'on ordered quantities' line is billable on confirm")

        po.action_create_invoice()

        self.assertEqual(po.invoice_count, 1, "exactly one vendor bill expected")
        bill = po.invoice_ids
        self.assertEqual(bill.move_type, 'in_invoice')
        self.assertEqual(bill.state, 'draft',
                         "the generated internal bill should be a draft")
