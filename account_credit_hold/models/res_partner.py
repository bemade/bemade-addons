from odoo import fields, models, api, _
from datetime import date


class Partner(models.Model):
    _inherit = "res.partner"

    postpone_hold_until = fields.Date(
        string="Postpone Hold",
        help="Grace period specific to this partner despite unpaid invoices.",
        tracking=True,
    )

    hold_bg = fields.Boolean(
        string="Hold (technical)",
        compute="_compute_hold_bg",
        store=True,
        default=False,
        compute_sudo=True,
        tracking=True,
    )
    on_hold = fields.Boolean(
        string="Account on Hold",
        help="Client account is on hold for unpaid overdue invoices.",
        compute="_compute_on_hold",
        compute_sudo=True,
    )

    @api.depends("postpone_hold_until", "hold_bg", "commercial_partner_id.hold_bg")
    def _compute_on_hold(self):
        for rec in self:
            # If the parent company is on hold, so are all its sub-contacts and subsidiaries
            if rec.commercial_partner_id != rec and rec.commercial_partner_id.hold_bg:
                if not (rec.commercial_partner_id.postpone_hold_until and rec.commercial_partner_id.postpone_hold_until > date.today()):
                    rec.on_hold = True
                    continue
            
            # If there is no parent company or the parent is not on hold, we compute for ourselves
            if rec.hold_bg and not (
                rec.postpone_hold_until and rec.postpone_hold_until > date.today()
            ):
                rec.on_hold = True
            else:
                rec.on_hold = False

    @api.autovacuum
    def _cleanup_expired_hold_postponements(self):
        expired_holds = self.search([("postpone_hold_until", "<=", date.today())])
        expired_holds.write({"postpone_hold_until": False})

    def action_credit_hold(self):
        for rec in self:
            rec.hold_bg = True
            rec.message_post(body=_("Placed on credit hold."))

    def action_lift_credit_hold(self):
        for rec in self:
            rec.hold_bg = False
            rec.message_post(body=_("Credit hold lifted."))

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

    def _get_followup_report(self, options):
        # Override to prevent hanging on PDF generation
        # Just set minimal required options without generating the report
        options.setdefault('attachment_ids', [])
        options['report_attachment_id'] = False

    def _execute_followup_partner(self, options=None):
        # Check if we need to place on credit hold before expensive operations
        should_hold = (
            self.followup_status == "in_need_of_action" and 
            self.followup_line_id and 
            hasattr(self.followup_line_id, 'account_hold') and 
            self.followup_line_id.account_hold
        )
        
        # If this is just for credit hold and we don't need reports/emails, skip heavy operations
        if options and options.get('credit_hold_only'):
            if should_hold:
                self.action_credit_hold()
            return should_hold
        
        # Otherwise run the full followup process
        res = super()._execute_followup_partner(options)
        
        # Apply credit hold after successful followup execution
        if should_hold:
            self.action_credit_hold()
            
        return res
