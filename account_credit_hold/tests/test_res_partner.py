# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo import Command, fields
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestResPartnerCreditHold(common.TransactionCase):
    """Tests for res.partner credit hold logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test company partner
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer",
            "is_company": True,
            "customer_rank": 1,
            "email": "test@example.com",
        })

        # Create a child contact under the company
        cls.child_contact = cls.env["res.partner"].create({
            "name": "Test Contact",
            "parent_id": cls.partner.id,
            "type": "contact",
        })

        # Remove existing followup lines to avoid interference
        cls.env["account_followup.followup.line"].search([]).unlink()

        # Create followup line with account_hold=True
        cls.followup_line_hold = cls.env["account_followup.followup.line"].create({
            "company_id": cls.env.company.id,
            "name": "Credit Hold Level",
            "delay": 30,
            "account_hold": True,
            "send_email": False,
        })

        # Create followup line WITHOUT account_hold
        cls.followup_line_no_hold = cls.env["account_followup.followup.line"].create({
            "company_id": cls.env.company.id,
            "name": "Reminder Level",
            "delay": 15,
            "account_hold": False,
            "send_email": False,
        })

    def _create_posted_invoice(self, partner, amount=1000.0, days_overdue=30):
        """Helper to create a posted invoice that is overdue."""
        due_date = fields.Date.today() - timedelta(days=days_overdue)
        invoice = self.env["account.move"].create({
            "partner_id": partner.id,
            "move_type": "out_invoice",
            "invoice_date": due_date,
            "invoice_date_due": due_date,
            "invoice_line_ids": [Command.create({
                "name": "Test Service",
                "quantity": 1.0,
                "price_unit": amount,
            })],
        })
        invoice.action_post()
        return invoice

    # ------------------------------------------------------------------
    # action_credit_hold
    # ------------------------------------------------------------------

    def test_action_credit_hold_sets_flags(self):
        """action_credit_hold must set on_hold and hold_bg to True."""
        self.partner.on_hold = False
        self.partner.hold_bg = False
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)
        self.assertTrue(self.partner.hold_bg)

    def test_action_credit_hold_idempotent(self):
        """Calling action_credit_hold twice must not raise."""
        self.partner.action_credit_hold()
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

    # ------------------------------------------------------------------
    # action_lift_credit_hold
    # ------------------------------------------------------------------

    def test_action_lift_credit_hold_clears_flags(self):
        """action_lift_credit_hold must clear on_hold, hold_bg, and postpone."""
        self.partner.on_hold = True
        self.partner.hold_bg = True
        self.partner.postpone_hold_until = fields.Datetime.now() + timedelta(days=5)
        self.partner.action_lift_credit_hold()
        self.assertFalse(self.partner.on_hold)
        self.assertFalse(self.partner.hold_bg)
        self.assertFalse(self.partner.postpone_hold_until)

    def test_action_lift_credit_hold_on_clean_partner(self):
        """Lifting hold on a partner not on hold must not raise."""
        self.partner.on_hold = False
        self.partner.hold_bg = False
        self.partner.action_lift_credit_hold()
        self.assertFalse(self.partner.on_hold)

    # ------------------------------------------------------------------
    # _compute_on_hold
    # ------------------------------------------------------------------

    def test_compute_on_hold_hold_bg_true_no_postpone(self):
        """hold_bg=True with no postpone date must result in on_hold=True."""
        self.partner.hold_bg = True
        self.partner.postpone_hold_until = False
        self.partner._compute_on_hold()
        self.assertTrue(self.partner.on_hold)

    def test_compute_on_hold_hold_bg_false(self):
        """hold_bg=False must result in on_hold=False."""
        self.partner.hold_bg = False
        self.partner.postpone_hold_until = False
        self.partner._compute_on_hold()
        self.assertFalse(self.partner.on_hold)

    def test_compute_on_hold_postpone_in_future(self):
        """hold_bg=True but postpone in future must result in on_hold=False."""
        self.partner.hold_bg = True
        self.partner.postpone_hold_until = datetime.now() + timedelta(days=10)
        self.partner._compute_on_hold()
        self.assertFalse(self.partner.on_hold)

    def test_compute_on_hold_postpone_in_past(self):
        """hold_bg=True with expired postpone must result in on_hold=True."""
        self.partner.hold_bg = True
        self.partner.postpone_hold_until = datetime.now() - timedelta(days=1)
        self.partner._compute_on_hold()
        self.assertTrue(self.partner.on_hold)

    def test_compute_on_hold_child_inherits_parent_hold(self):
        """Child contact must be on_hold when parent company hold_bg is True."""
        self.partner.hold_bg = True
        self.partner.postpone_hold_until = False
        self.child_contact._compute_on_hold()
        self.assertTrue(self.child_contact.on_hold)

    def test_compute_on_hold_child_not_held_when_parent_postponed(self):
        """Child contact must NOT be on_hold when parent postpone is in future."""
        self.partner.hold_bg = True
        self.partner.postpone_hold_until = datetime.now() + timedelta(days=10)
        self.child_contact._compute_on_hold()
        self.assertFalse(self.child_contact.on_hold)

    # ------------------------------------------------------------------
    # _compute_total_due
    # ------------------------------------------------------------------

    def test_compute_total_due_no_invoices(self):
        """Partner with no invoices must have total_due=0."""
        partner = self.env["res.partner"].create({
            "name": "No Invoice Partner",
            "customer_rank": 1,
        })
        partner._compute_total_due()
        self.assertEqual(partner.total_due, 0.0)

    def test_compute_total_due_with_posted_invoice(self):
        """Partner with a posted unpaid invoice must have correct total_due."""
        partner = self.env["res.partner"].create({
            "name": "Invoice Partner",
            "customer_rank": 1,
        })
        self._create_posted_invoice(partner, amount=500.0)
        partner._compute_total_due()
        self.assertAlmostEqual(partner.total_due, 500.0, places=2)

    def test_compute_total_due_with_multiple_invoices(self):
        """Total due must sum all posted unpaid invoices."""
        partner = self.env["res.partner"].create({
            "name": "Multi Invoice Partner",
            "customer_rank": 1,
        })
        self._create_posted_invoice(partner, amount=300.0)
        self._create_posted_invoice(partner, amount=200.0)
        partner._compute_total_due()
        self.assertAlmostEqual(partner.total_due, 500.0, places=2)

    # ------------------------------------------------------------------
    # _should_hold
    # ------------------------------------------------------------------

    def test_should_hold_with_hold_followup_line(self):
        """Partner with a followup line that has account_hold=True must return True."""
        self.partner.followup_line_id = self.followup_line_hold
        self.assertTrue(self.partner._should_hold())

    def test_should_hold_with_no_hold_followup_line(self):
        """Partner with a followup line that has account_hold=False must return False."""
        self.partner.followup_line_id = self.followup_line_no_hold
        self.assertFalse(self.partner._should_hold())

    def test_should_hold_without_followup_line(self):
        """Partner without a followup line must return False (falsy)."""
        self.partner.followup_line_id = False
        self.assertFalse(self.partner._should_hold())

    # ------------------------------------------------------------------
    # _compute_hold_bg
    # ------------------------------------------------------------------

    def test_compute_hold_bg_no_action_no_level_clears_hold_bg(self):
        """hold_bg must be cleared when status is no_action_needed and no level."""
        self.partner.hold_bg = True
        # Force status without triggering full compute chain
        self.partner.followup_line_id = False
        self.partner.followup_status = "no_action_needed"
        self.partner._compute_hold_bg()
        self.assertFalse(self.partner.hold_bg)

    def test_compute_hold_bg_preserves_existing_when_in_action(self):
        """hold_bg must stay unchanged when status is in_need_of_action."""
        self.partner.hold_bg = True
        self.partner.followup_line_id = self.followup_line_hold
        self.partner.followup_status = "in_need_of_action"
        self.partner._compute_hold_bg()
        self.assertTrue(self.partner.hold_bg)
