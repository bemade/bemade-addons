from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class CbetCertification(models.Model):
    """UC-EVL-10 / UC-VAL-01 — a time-limited competency certification for one
    employee. Kept out of hr.employee.skill (D1); the coarse qualification skill
    is granted separately by the qualification engine (UC-STD-03)."""

    _name = "cbet.certification"
    _description = "CBET Competency Certification"
    _order = "valid_from desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    employee_id = fields.Many2one(
        "hr.employee", required=True, ondelete="restrict", index=True, tracking=True,
    )
    competency_id = fields.Many2one(
        "cbet.competency", required=True, ondelete="restrict", index=True, tracking=True,
    )
    competency_version_id = fields.Many2one(
        "cbet.competency.version", string="Pinned version", ondelete="restrict",
    )
    valid_from = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    valid_to = fields.Date(tracking=True)
    active = fields.Boolean(default=True)
    source_evaluation_ids = fields.Many2many("cbet.evaluation", string="Source evaluations")

    state = fields.Selection(
        [
            ("valid", "Valid"),
            ("expiring", "Expiring soon"),
            ("expired", "Expired"),
            ("superseded", "Superseded"),
        ],
        compute="_compute_state",
        search="_search_state",
    )

    def _horizon_months(self):
        return self.env.company.cbet_expiry_horizon_months or 3

    @api.depends("valid_from", "valid_to", "active")
    def _compute_state(self):
        today = fields.Date.context_today(self)
        horizon = self._horizon_months()
        for cert in self:
            if not cert.active:
                cert.state = "superseded"
            elif cert.valid_to and cert.valid_to < today:
                cert.state = "expired"
            elif cert.valid_to and cert.valid_to <= today + relativedelta(months=horizon):
                cert.state = "expiring"
            else:
                cert.state = "valid"

    def _search_state(self, operator, value):
        # Only equality on the common states is supported (enough for the crons/UI).
        today = fields.Date.context_today(self)
        horizon_date = today + relativedelta(months=self._horizon_months())
        domains = {
            "expired": [("active", "=", True), ("valid_to", "<", today)],
            "expiring": [("active", "=", True), ("valid_to", ">=", today),
                         ("valid_to", "<=", horizon_date)],
            "valid": ["|", ("valid_to", "=", False), ("valid_to", ">", horizon_date),
                      ("active", "=", True)],
            "superseded": [("active", "=", False)],
        }
        domain = domains.get(value, [])
        if operator in ("!=", "not in"):
            return ["!"] + domain
        return domain

    def _is_currently_valid(self):
        """Certification is usable (not expired, not superseded)."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self.active and (not self.valid_to or self.valid_to >= today)

    # ------------------------------------------------------------------
    # UC-VAL-01 — competency-level expiry engine (separate from the native
    # hr.employee.skill tie-back cron; both fire by design, AC3).
    # ------------------------------------------------------------------
    def _expiry_responsible(self):
        """UC-VAL-01 AC2 — the employee's manager (parent_id), fallback Manager."""
        self.ensure_one()
        responsible = self.employee_id.parent_id.user_id
        if not responsible:
            responsible = self.env.ref(
                "hr_skills_cbet.group_cbet_manager").user_ids[:1]
        return responsible

    @api.model
    def _cron_expiry_activities(self):
        today = fields.Date.context_today(self)
        horizon = today + relativedelta(months=self._horizon_months())
        certs = self.search([
            ("active", "=", True),
            ("valid_to", "!=", False),
            ("valid_to", "<=", horizon),
        ])
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        model_id = self.env["ir.model"]._get_id(self._name)
        affected_employees = self.env["hr.employee"]
        for cert in certs:
            responsible = cert._expiry_responsible()
            if not responsible:
                continue
            # AC2 — one activity per certification (no spam).
            existing = self.env["mail.activity"].search_count([
                ("res_model_id", "=", model_id),
                ("res_id", "=", cert.id),
                ("activity_type_id", "=", activity_type.id),
            ])
            if not existing:
                cert.activity_schedule(
                    "mail.mail_activity_data_todo",
                    date_deadline=cert.valid_to,
                    summary=self.env._("Certification expiring: %s", cert.competency_id.code),
                    user_id=responsible.id,
                )
            if cert.valid_to < today:
                affected_employees |= cert.employee_id
        # AC4 — expiry suspends qualifications in the closed set.
        for employee in affected_employees:
            comps = self.search([("employee_id", "=", employee.id)]).mapped("competency_id")
            self.env["cbet.qualification"]._recompute_for_employee(employee, comps)
        return True
