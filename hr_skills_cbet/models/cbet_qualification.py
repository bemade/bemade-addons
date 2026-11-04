from odoo import api, fields, models


class CbetQualification(models.Model):
    """UC-STD-02/03 — an employee's state against a qualification standard, with
    the coarse hr.skill tie-back."""

    _name = "cbet.qualification"
    _description = "CBET Employee Qualification"
    _order = "employee_id, standard_id"
    _inherit = ["mail.thread"]

    employee_id = fields.Many2one(
        "hr.employee", required=True, ondelete="cascade", index=True,
    )
    standard_id = fields.Many2one(
        "cbet.standard", required=True, ondelete="cascade", index=True,
    )
    state = fields.Selection(
        [
            ("in_progress", "In progress"),
            ("qualified", "Qualified"),
            ("suspended", "Suspended"),
        ],
        default="in_progress",
        required=True,
        tracking=True,
        copy=False,
    )
    n_required = fields.Integer(string="# required", readonly=True)
    n_certified = fields.Integer(string="# certified", readonly=True)
    percent_complete = fields.Float(string="% complete", readonly=True)
    active = fields.Boolean(default=True, tracking=True)
    from_job = fields.Boolean(
        string="Required by job position", readonly=True, copy=False,
        help="Created because the employee's job position requires the standard; "
             "archived when it no longer does.",
    )
    tie_back_skill_row_id = fields.Many2one(
        "hr.employee.skill", string="Tie-back skill row", copy=False,
    )

    _emp_std_uniq = models.Constraint(
        "unique(employee_id, standard_id)",
        "This employee already has a qualification record for this standard.",
    )

    # ------------------------------------------------------------------
    @api.model
    def _get_or_create(self, employee, standard):
        """The employee's qualification on the standard; an archived one is
        reactivated rather than duplicated (unique employee/standard)."""
        qual = self.with_context(active_test=False).search([
            ("employee_id", "=", employee.id), ("standard_id", "=", standard.id),
        ], limit=1)
        if not qual:
            qual = self.create({"employee_id": employee.id, "standard_id": standard.id})
        elif not qual.active:
            qual.active = True
        return qual.with_context(active_test=self.env.context.get("active_test", True))

    @api.model
    def _sync_job_requirements(self, employees):
        """UC-STD-06 — align the employees' job-derived qualifications with the
        standards their job position requires.

        Missing → created (or reactivated) with from_job=True and recomputed.
        A from_job qualification the position no longer requires — or held by an
        archived employee — is archived, never deleted (history stays).
        Qualifications created by hand (from_job=False) are left alone.
        """
        employees = employees.sudo().with_context(active_test=False).exists()
        if not employees:
            return True
        Qual = self.sudo().with_context(active_test=False)
        existing = {
            (q.employee_id.id, q.standard_id.id): q
            for q in Qual.search([("employee_id", "in", employees.ids)])
        }
        to_create, to_recompute, to_archive = [], Qual.browse(), Qual.browse()
        for employee in employees:
            required = (employee.job_id.cbet_standard_ids.filtered("active")
                        if employee.active else self.env["cbet.standard"])
            for standard in required:
                qual = existing.get((employee.id, standard.id))
                if not qual:
                    to_create.append({
                        "employee_id": employee.id,
                        "standard_id": standard.id,
                        "from_job": True,
                    })
                elif not qual.active:
                    qual.write({"active": True, "from_job": True})
                    to_recompute |= qual
            for (emp_id, std_id), qual in existing.items():
                if (emp_id == employee.id and qual.active and qual.from_job
                        and std_id not in required.ids):
                    to_archive |= qual
        to_archive.write({"active": False})
        to_recompute |= Qual.create(to_create)
        to_recompute._recompute()
        return True

    def _valid_certs_in_closure(self):
        """Employee's currently-valid certifications whose competency is in the
        standard's closed requirement set."""
        self.ensure_one()
        closed = self.standard_id.closed_competency_ids
        certs = self.env["cbet.certification"].search([
            ("employee_id", "=", self.employee_id.id),
            ("competency_id", "in", closed.ids),
            ("active", "=", True),
        ])
        return certs.filtered(lambda c: c._is_currently_valid())

    def _recompute(self):
        for qual in self:
            old_state = qual.state
            closed = qual.standard_id.closed_competency_ids
            valid_certs = qual._valid_certs_in_closure()
            valid_comps = valid_certs.mapped("competency_id")
            qual.n_required = len(closed)
            qual.n_certified = len(closed & valid_comps)
            qual.percent_complete = (
                100.0 * qual.n_certified / qual.n_required if qual.n_required else 0.0
            )
            all_valid = closed and (closed & valid_comps) == closed
            if all_valid:
                qual.state = "qualified"
            elif qual.state in ("qualified", "suspended"):
                # UC-STD-02 AC3 — a lapse suspends, does not reset; recomputing
                # a suspended qualification again keeps it suspended.
                qual.state = "suspended"
            else:
                qual.state = "in_progress"
            qual._sync_tieback(valid_certs)
            if qual.state != old_state:
                # Explicit audit line — automatic field-tracking misses the first
                # grant (state change in the same transaction as record creation).
                qual._message_log(body=self.env._(
                    "Qualification: %(state)s — %(n)s/%(req)s certified (%(pct).0f%%)",
                    state=dict(self._fields["state"]._description_selection(self.env))[qual.state],
                    n=qual.n_certified, req=qual.n_required, pct=qual.percent_complete))
        return True

    def _sync_tieback(self, valid_certs=None):
        """UC-STD-03 — keep the coarse hr.employee.skill row in sync.

        valid_to = rolling min of the whole closed set's cert expiries, updated
        in place; one open row per qualification period, closed on lapse.
        """
        self.ensure_one()
        skill = self.standard_id.skill_id
        if not skill:
            return
        if valid_certs is None:
            valid_certs = self._valid_certs_in_closure()
        today = fields.Date.context_today(self)
        expiries = [c.valid_to for c in valid_certs if c.valid_to]
        rolling_min = min(expiries) if expiries else False

        row = self.tie_back_skill_row_id
        if self.state == "qualified":
            if row and row.exists():
                # Update valid_to in place as the min moves (no close/reopen).
                if row.valid_to != rolling_min:
                    row.valid_to = rolling_min
            else:
                self.tie_back_skill_row_id = self._create_tieback_row(
                    skill, today, rolling_min)
        else:
            # Suspended / in_progress: close the open row on a real lapse.
            if row and row.exists() and (not row.valid_to or row.valid_to >= today):
                row.valid_to = today
            self.tie_back_skill_row_id = False

    def _create_tieback_row(self, skill, valid_from, valid_to):
        self.ensure_one()
        skill_type = skill.skill_type_id
        level = skill_type.skill_level_ids.sorted("level_progress")[-1:]
        return self.env["hr.employee.skill"].create({
            "employee_id": self.employee_id.id,
            "skill_type_id": skill_type.id,
            "skill_id": skill.id,
            "skill_level_id": level.id,
            "valid_from": valid_from,
            "valid_to": valid_to,
        })

    # Entry point used by certification issuance / entry / expiry.
    @api.model
    def _recompute_for_employee(self, employee, competencies):
        """Recompute the employee's EXISTING active qualifications whose closed
        set touches any of the given competencies.

        It never creates one: which standards an employee qualifies against is
        decided by their job position (UC-STD-06) or by hand, not by whatever
        certificate they happen to hold."""
        # sudo: derived state — the evaluator or manager who enters the
        # certificate may not read every qualification of the employee.
        quals = self.sudo().search([("employee_id", "=", employee.id)])
        quals.filtered(
            lambda q: q.standard_id.closed_competency_ids & competencies)._recompute()
