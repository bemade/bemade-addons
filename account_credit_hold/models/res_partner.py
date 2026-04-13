# -*- coding: utf-8 -*-
from datetime import date
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

    @api.depends("postpone_hold_until", "hold_bg", "commercial_partner_id.hold_bg")
    def _compute_on_hold(self):
        for rec in self:
            # If the parent company is on hold, so are all its sub-contacts and subsidiaries
            if rec.commercial_partner_id != rec and rec.commercial_partner_id.hold_bg:
                if not (
                    rec.commercial_partner_id.postpone_hold_until
                    and rec.commercial_partner_id.postpone_hold_until > date.today()
                ):
                    rec.on_hold = True
                    continue

            # If there is no parent company or the parent is not on hold, we compute for ourselves
            if rec.hold_bg and not (
                rec.postpone_hold_until and rec.postpone_hold_until > date.today()
            ):
                rec.on_hold = True
            else:
                rec.on_hold = False

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

    @api.model
    def _get_first_followup_level(self):
        return self.env["account_followup.followup.line"].search(
            [("company_id", "parent_of", self.env.company.id)],
            order="delay asc",
            limit=1,
        )

    @api.depends("followup_status", "followup_line_id")
    def _compute_hold_bg(self):
        first_followup_level = self._get_first_followup_level()
        for rec in self:
            prev_hold_bg = rec.hold_bg
            level = rec.followup_line_id
            if rec.followup_status == "no_action_needed" and not level:
                rec.hold_bg = False
            else:
                rec.hold_bg = prev_hold_bg

    def _execute_followup_partner(self, options=None):
        # Check if we need to place on credit hold before expensive operations
        should_hold = self._should_hold()

        # If this is just for credit hold and we don't need reports/emails, skip heavy operations
        if options and options.get("credit_hold_only"):
            if should_hold:
                self.action_credit_hold()
            return should_hold

        # Otherwise run the full followup process
        res = super()._execute_followup_partner(options)

        # Apply credit hold after successful followup execution
        if should_hold:
            self.action_credit_hold()
            res = True

        return res

    @api.depends("unreconciled_aml_ids", "followup_next_action_date")
    @api.depends_context("company", "allowed_company_ids")
    def _compute_followup_status(self):
        super()._compute_followup_status()
        for rec in self:
            if rec.hold_bg and not rec._should_hold():
                rec.action_lift_credit_hold()

    def _should_hold(self):
        self.ensure_one()
        return self.followup_line_id and self.followup_line_id.account_hold

    def action_credit_hold(self):
        """Place partner on credit hold."""
        self.ensure_one()
        self.on_hold = True
        self.hold_bg = True
