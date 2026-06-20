import operator as _op
from datetime import date

from odoo import fields, models, api, _


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
        search="_search_on_hold",
    )
    # Upstream account_followup defines total_due as a non-stored Monetary
    # without a search method, which makes modern Odoo's view validator reject
    # the "Overdue Invoices" filter (domain=[('total_due','>',0)]) in
    # views/res_partner_views.xml. Add a search driver here — keeps the field
    # non-stored as upstream intends.
    total_due = fields.Monetary(search="_search_total_due")

    def _search_on_hold(self, operator, value):
        """Search-driver for the non-stored `on_hold` field.

        Mirrors the truth table in ``_compute_on_hold``:

          on_hold = True  iff
              (self.commercial_partner_id has hold_bg=True and no active postpone)
           OR (self.hold_bg=True and no active postpone on self)

        We resolve to a set of ids and return an ``('id', 'in', ...)`` domain.
        """
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError(
                _("Unsupported operator %r for on_hold search.") % operator
            )
        today = date.today()
        # Partners whose own hold_bg is on with no active postpone.
        held_directly = self.with_context(active_test=False).search([
            ("hold_bg", "=", True),
            "|",
            ("postpone_hold_until", "=", False),
            ("postpone_hold_until", "<=", today),
        ])
        # Plus any partner whose commercial_partner_id is in that held set
        # (covers sub-contacts inheriting hold from their commercial entity).
        held_via_commercial = self.with_context(active_test=False).search([
            ("commercial_partner_id", "in", held_directly.ids),
        ])
        held_ids = (held_directly | held_via_commercial).ids
        is_match = value if operator == "=" else not value
        return [("id", "in" if is_match else "not in", held_ids)]

    def _search_total_due(self, operator, value):
        """Search-driver for the non-stored upstream `total_due` Monetary.

        Aggregates posted unreconciled receivable AMLs per partner (same
        domain ``_compute_total_due`` uses upstream) and applies the
        comparison. Partners with no matching AMLs (total_due == 0) are
        included if 0 satisfies the operator.
        """
        op_func_map = {
            "=": _op.eq,
            "!=": _op.ne,
            ">": _op.gt,
            "<": _op.lt,
            ">=": _op.ge,
            "<=": _op.le,
        }
        if operator not in op_func_map:
            raise NotImplementedError(
                _("Unsupported operator %r for total_due search.") % operator
            )
        op_func = op_func_map[operator]
        aml_groups = self.env["account.move.line"]._read_group(
            domain=[
                ("reconciled", "=", False),
                ("account_id.account_type", "=", "asset_receivable"),
                ("parent_state", "=", "posted"),
            ],
            groupby=["partner_id"],
            aggregates=["amount_residual:sum"],
        )
        explicit_match = {p.id for p, total in aml_groups if op_func(total, value)}
        explicit_partners = {p.id for p, _ in aml_groups}
        # If 0 satisfies the operator, partners with no AMLs (implicit total 0)
        # should also match — express that as a "not in" on the partners that
        # explicitly do NOT match.
        if op_func(0.0, value):
            return [("id", "not in", list(explicit_partners - explicit_match))]
        return [("id", "in", list(explicit_match))]

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
