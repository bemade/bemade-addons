from datetime import datetime

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCovVendorPOReceivedQty(TransactionCase):
    """Vendor-PO lines built from delivered timesheets must be marked received.

    The therapist fee products are services billed on *ordered* quantities, so a
    confirmed PO is billable without a goods receipt. But Odoo 19's purchase
    accrual reports (Accounting > Review > Purchases > "Billed Not Received" and
    "Bill To Receive", both purchase.order.line based) flag every line where
    ``qty_invoiced != qty_received``. Since these services never get a receipt,
    each billed line sits forever in "Billed Not Received" as a phantom accrual.

    The timesheet is itself the proof the therapist delivered the service, so the
    wizard should mark the line received (qty_received == ordered qty) when it
    creates it. Received then equals Billed and the line drops out of both
    accrual reports.

    Acceptance criteria
    -------------------
    1. Every PO line the wizard creates has ``qty_received == product_qty``.
    2. After confirming and billing the PO, ``qty_invoiced == qty_received`` on
       every line (balanced -> excluded from the accrual reports).
    """

    COV_PARAM = 'bemade_sports_clinic.product_event_coverage_vendor_id'
    TRV_PARAM = 'bemade_sports_clinic.product_event_travel_vendor_id'
    CLI_PARAM = 'bemade_sports_clinic.product_event_clinic_vendor_id'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env['ir.config_parameter'].sudo()

        cls.team = cls.env['sports.team'].create({'name': 'Recv Team'})
        cls.venue = cls.env['res.partner'].create({'name': 'Recv Arena', 'is_venue': True})
        cls.therapist = cls.env['res.users'].create({
            'name': 'Recv Therapist', 'login': 'recv_therapist', 'email': 'recv_t@example.com',
        })
        cls.event = cls.env['sports.event'].create({
            'name': 'Recv Game',
            'event_type': 'game',
            'team_ids': [Command.set([cls.team.id])],
            'venue_id': cls.venue.id,
            'date_start': datetime(2026, 1, 5, 10, 0),
            'date_end': datetime(2026, 1, 5, 12, 0),
            'state': 'confirmed',
        })

        # Service fees billed on ordered quantities (mirrors the live products).
        def _fee(name):
            return cls.env['product.product'].create({
                'name': name, 'type': 'service', 'purchase_method': 'purchase',
                'standard_price': 30.0,
            })
        cls.prod_cov = _fee('Coverage (Vendor)')
        cls.prod_trv = _fee('Travel (Vendor)')
        cls.prod_cli = _fee('Clinic (Vendor)')
        cls.ICP.set_param(cls.COV_PARAM, str(cls.prod_cov.id))
        cls.ICP.set_param(cls.TRV_PARAM, str(cls.prod_trv.id))
        cls.ICP.set_param(cls.CLI_PARAM, str(cls.prod_cli.id))

    def _wizard(self, timesheet_ids, **vals):
        return self.env['sports.event.vendor.po.wizard'].with_context(
            active_model='sports.event.timesheet', active_ids=timesheet_ids,
        ).create(vals)

    def _run_wizard(self):
        ts = self.env['sports.event.timesheet'].create({
            'event_id': self.event.id, 'user_id': self.therapist.id,
            'coverage_start': datetime(2026, 1, 5, 10, 0),
            'coverage_end': datetime(2026, 1, 5, 12, 0),
            'travel_start': datetime(2026, 1, 5, 9, 0),
            'travel_end': datetime(2026, 1, 5, 13, 0),
        })
        wizard = self._wizard([ts.id])
        wizard.create_new_if_missing = True
        wizard.action_add_to_vendor_po()
        return ts.vendor_purchase_order_id

    def test_lines_marked_received_on_creation(self):
        po = self._run_wizard()
        self.assertTrue(po.order_line, "wizard should have created PO lines")
        for line in po.order_line:
            self.assertEqual(
                line.qty_received, line.product_qty,
                "service line should be marked fully received so it stays out "
                "of the 'Billed Not Received' accrual report",
            )

    def test_billed_equals_received_after_billing(self):
        po = self._run_wizard()
        po.button_confirm()
        po.action_create_invoice()
        for line in po.order_line:
            self.assertEqual(
                line.qty_invoiced, line.qty_received,
                "billed qty must equal received qty so the line is excluded "
                "from both purchase accrual reports",
            )
