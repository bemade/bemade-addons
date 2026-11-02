from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.fields import Domain


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
    valid_to = fields.Date(
        compute="_compute_valid_to", store=True, readonly=False, precompute=True,
        tracking=True,
        help="Defaults to the start date plus the competency's validity (or the "
             "company default); can be changed.",
    )
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

    @api.depends("valid_from", "competency_id")
    def _compute_valid_to(self):
        for cert in self:
            if not (cert.valid_from and cert.competency_id):
                continue
            months = (cert.competency_id.validity_months
                      or cert.env.company.cbet_default_validity_months)
            if months:
                cert.valid_to = cert.valid_from + relativedelta(months=months)

    @api.depends("employee_id", "competency_id")
    def _compute_display_name(self):
        for cert in self:
            parts = [cert.employee_id.name, cert.competency_id.code]
            cert.display_name = " — ".join(p for p in parts if p) or False

    # Recomputing qualifications on these keeps them in step with what is
    # entered by hand, not only with evaluation issuance (UC-VAL-02 AC4).
    _QUALIFICATION_FIELDS = {"valid_to", "valid_from", "active", "employee_id",
                             "competency_id"}

    @api.model_create_multi
    def create(self, vals_list):
        certs = super().create(vals_list)
        certs._supersede_previous()
        certs._recompute_qualifications()
        return certs

    def write(self, vals):
        touched = self._QUALIFICATION_FIELDS & set(vals)
        before = self.mapped(lambda c: (c.employee_id, c.competency_id)) if touched else []
        res = super().write(vals)
        if touched:
            self._recompute_qualifications(extra_pairs=before)
        return res

    def _supersede_previous(self):
        """UC-EVL-10 AC2 / UC-VAL-02 AC3 — a new active certificate archives the
        employee's older active one(s) on the same competency. A back-dated entry
        (older valid_from) never archives a newer one."""
        for cert in self.filtered("active"):
            prior = self.search([
                ("id", "not in", self.ids),
                ("employee_id", "=", cert.employee_id.id),
                ("competency_id", "=", cert.competency_id.id),
                ("active", "=", True),
                ("valid_from", "<=", cert.valid_from),
            ])
            if prior:
                prior.active = False

    def _recompute_qualifications(self, extra_pairs=()):
        Qualification = self.env["cbet.qualification"]
        by_employee = {}
        pairs = list(extra_pairs) + [(c.employee_id, c.competency_id) for c in self]
        for employee, competency in pairs:
            if employee and competency:
                by_employee.setdefault(employee, competency.browse())
                by_employee[employee] |= competency
        for employee, competencies in by_employee.items():
            Qualification._recompute_for_employee(employee, competencies)

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
        """Search on the computed state. The 19.0 ORM hands '=' / 'in' a
        collection of values; a scalar is accepted too."""
        if operator not in ("=", "!=", "in", "not in"):
            return NotImplemented
        if isinstance(value, str) or not hasattr(value, "__iter__"):
            values = [value]
        else:
            values = list(value)
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
        domain = Domain.OR(domains[v] for v in values if v in domains)
        if operator in ("!=", "not in"):
            return ~domain
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
            company = cert.employee_id.company_id or self.env.company
            hr_responsible = company.cbet_hr_responsible_id
            # AC2 — one to-do per (certification, user), whatever the run count:
            # the manager's, and the HR responsible's when set and different.
            users = cert._expiry_responsible() | hr_responsible
            already = self.env["mail.activity"].search([
                ("res_model_id", "=", model_id),
                ("res_id", "=", cert.id),
                ("activity_type_id", "=", activity_type.id),
            ]).user_id
            for user in users - already:
                cert.activity_schedule(
                    "mail.mail_activity_data_todo",
                    date_deadline=cert.valid_to,
                    summary=self.env._("Certification expiring: %s", cert.competency_id.code),
                    user_id=user.id,
                )
            if cert.valid_to < today:
                affected_employees |= cert.employee_id
        # AC4 — expiry suspends qualifications in the closed set.
        for employee in affected_employees:
            comps = self.search([("employee_id", "=", employee.id)]).mapped("competency_id")
            self.env["cbet.qualification"]._recompute_for_employee(employee, comps)
        return True
