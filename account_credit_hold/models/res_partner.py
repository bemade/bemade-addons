# -*- coding: utf-8 -*-
from odoo import fields, models, api


class ResPartner(models.Model):
    """Extend partner with credit hold functionality."""
    _inherit = "res.partner"

    on_hold = fields.Boolean(
        string="On Credit Hold",
        help="Customer is on credit hold, restricting new order confirmations.",
        default=False,
    )
    hold_bg = fields.Boolean(
        string="Hold Background",
        help="Internal field for background processing of credit hold.",
        default=False,
    )
    postpone_hold_until = fields.Datetime(
        string="Postpone Hold Until",
        help="Temporarily postpone credit hold until this date.",
    )
    followup_status = fields.Selection([
        ('no_action_needed', 'No Action Needed'),
        ('in_need_of_action', 'In Need of Action'),
        ('overdue', 'Overdue'),
    ], string="Followup Status", compute="_compute_followup_status", store=True)
    total_due = fields.Float(
        string="Total Due",
        compute="_compute_total_due",
        store=True,
        help="Total amount due from all overdue invoices"
    )

    @api.depends('invoice_ids', 'invoice_ids.state', 'invoice_ids.amount_residual', 'invoice_ids.invoice_date_due')
    def _compute_followup_status(self):
        """Compute followup status based on overdue invoices."""
        for partner in self:
            overdue_invoices = partner.invoice_ids.filtered(
                lambda inv: inv.state == 'posted' and 
                inv.amount_residual > 0 and 
                inv.invoice_date_due and 
                inv.invoice_date_due < fields.Date.today()
            )
            
            if not overdue_invoices:
                partner.followup_status = 'no_action_needed'
            else:
                total_overdue = sum(overdue_invoices.mapped('amount_residual'))
                if total_overdue > 0:
                    partner.followup_status = 'in_need_of_action'
                else:
                    partner.followup_status = 'no_action_needed'

    @api.depends('invoice_ids', 'invoice_ids.state', 'invoice_ids.amount_residual', 'invoice_ids.invoice_date_due')
    def _compute_total_due(self):
        """Compute total amount due from all invoices."""
        for partner in self:
            total_due = 0.0
            for invoice in partner.invoice_ids:
                if invoice.state == 'posted' and invoice.amount_residual > 0:
                    total_due += invoice.amount_residual
            partner.total_due = total_due

    def action_lift_credit_hold(self):
        """Lift credit hold for this partner."""
        self.ensure_one()
        self.on_hold = False
        self.hold_bg = False
        self.postpone_hold_until = False

    def action_credit_hold(self):
        """Place partner on credit hold."""
        self.ensure_one()
        self.on_hold = True
        self.hold_bg = True
