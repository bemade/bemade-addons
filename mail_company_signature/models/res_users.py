from contextlib import contextmanager

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = "res.users"

    # groups=False is deliberate: the flag must stay readable by plain internal
    # users for the readonly modifier on the signature in My Preferences
    # (the company field is restricted to base.group_system). The value is a
    # harmless boolean.
    company_signature_enforced = fields.Boolean(
        compute="_compute_company_signature_enforced",
        groups=False,
    )
    company_signature_manual = fields.Boolean(
        string="Manage own signature",
        groups="base.group_system",
        copy=False,
        default=False,
        help="Exempt this user from the company-standard signature: they "
        "write their own. Unticking it regenerates the signature.",
    )
    personal_signature_backup = fields.Html(
        string="Personal signature backup",
        groups="base.group_system",
        copy=False,
        help="Signature the user had before the company-standard signature "
        "was enforced.",
    )
    signature_is_generated = fields.Boolean(
        groups="base.group_system",
        copy=False,
        default=False,
        help="Set when the current signature was produced by the company "
        "template rather than written by a person.",
    )

    @api.depends(
        "company_id",
        "company_signature_manual",
        "employee_ids",
        "employee_ids.active",
        "employee_ids.company_id",
    )
    def _compute_company_signature_enforced(self):
        enforced = self._company_signature_enforced_users()
        for user in self:
            user.company_signature_enforced = user in enforced

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def _is_company_signature_enforced(self):
        self.ensure_one()
        return bool(self._company_signature_enforced_users())

    def _company_signature_enforced_users(self):
        """Users subject to the policy: internal, not opted out, of an
        enforcing company, and with an active employee in that company."""
        candidates = self.filtered(
            lambda u: not u.sudo().share
            and not u.sudo().company_signature_manual
            and u.sudo().company_id.company_signature_enforced
        )
        if not candidates:
            return candidates
        employees = candidates._company_signature_employees()
        return candidates.filtered(lambda u: u.id in employees)

    def _company_signature_employees(self):
        """Return {user id: the user's active employee in their own company}.

        Does not use ``employee_ids`` (its domain depends on ``env.company``).
        """
        users = self.sudo()
        origin_ids = [uid for uid in users._origin.ids if uid]
        if not origin_ids:
            return {}
        employees = (
            self.env["hr.employee"]
            .sudo()
            .with_context(active_test=True)
            .search(
                [
                    ("user_id", "in", origin_ids),
                    ("company_id", "in", users.company_id.ids),
                ],
                order="id",
            )
        )
        emp_by_key = {}
        for emp in employees:
            emp_by_key.setdefault((emp.user_id.id, emp.company_id.id), emp)
        result = {}
        for user in users:
            emp = emp_by_key.get((user._origin.id, user.company_id.id))
            if emp:
                result[user.id] = emp
        return result

    @contextmanager
    def _company_signature_transition(self):
        """Apply the enforced/released transitions caused by the wrapped code.

        Keyed on the real before/after enforced state of the users: newly
        enforced users get their personal signature backed up (unless it was
        itself generated) and regenerated; released users keep the last
        generated signature, flagged as generated.
        """
        users = self.sudo().with_context(active_test=False)
        enforced_before = users._company_signature_enforced_users()
        prior = {
            user.id: user.signature
            for user in (users - enforced_before)
            if not user.signature_is_generated
        }
        yield
        enforced_after = users._company_signature_enforced_users()
        newly = enforced_after - enforced_before
        for user in newly:
            if user.id in prior:
                user.personal_signature_backup = prior[user.id]
        if newly:
            self.env.add_to_compute(self._fields["signature"], newly)
        released = enforced_before - enforced_after
        if released:
            released.signature_is_generated = True

    @api.depends(
        "name",
        "email",
        "share",
        "company_id",
        "company_id.company_signature_enforced",
        "company_id.company_signature_template",
        "company_id.company_signature_notice",
        "company_id.company_signature_notice_until",
        "company_signature_manual",
        "company_id.name",
        "company_id.phone",
        "company_id.email",
        "company_id.website",
        "employee_ids",
        "employee_ids.active",
        "employee_ids.company_id",
        "employee_ids.name",
        "employee_ids.job_title",
        "employee_ids.job_id",
        "employee_ids.job_id.name",
        "employee_ids.work_phone",
        "employee_ids.mobile_phone",
        "employee_ids.work_email",
    )
    def _compute_signature(self):
        enforced = self._company_signature_enforced_users()
        super(ResUsers, self - enforced)._compute_signature()
        if not enforced:
            return
        values_by_user = enforced.sudo()._company_signature_values()
        for user in enforced:
            user.signature = user.company_id.sudo()._company_signature_render(
                values_by_user[user.id]
            )

    def _company_signature_values(self):
        """Placeholder values for every user of the recordset, in one batch.

        Only an employee of the user's own company counts.
        """
        emp_by_user = self._company_signature_employees()
        result = {}
        notices = {}
        for user in self:
            emp = emp_by_user.get(user.id)
            company = user.company_id
            if company.id not in notices:
                notices[company.id] = company._company_signature_notice_value()
            result[user.id] = {
                "name": (emp.name if emp else "") or user.name or "",
                "job_title": (emp.job_title if emp else "") or "",
                "job_position": self._company_signature_job_position(emp),
                "company_notice": notices[company.id],
                "work_phone": (emp.work_phone if emp else "") or "",
                "mobile_phone": (emp.mobile_phone if emp else "") or "",
                "work_email": (emp.work_email if emp else "") or user.email or "",
                "company_name": company.name or "",
                "company_phone": company.phone or "",
                "company_email": company.email or "",
                "company_website": company.website or "",
            }
        return result

    @api.model
    def _company_signature_job_position(self, employee):
        """Job position as "FR / EN", one value when equal or untranslated.

        Without a job position, the employee's job title.
        """
        if not employee:
            return ""
        job = employee.job_id
        if not job:
            return (employee.job_title or "").strip()
        french = (job.with_context(lang="fr_FR").name or "").strip()
        english = (job.with_context(lang="en_US").name or "").strip()
        if not french or french == english:
            return english
        if not english:
            return french
        return "%s / %s" % (french, english)

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        enforced = users._company_signature_enforced_users()
        if enforced:
            # Whatever signature was passed in vals loses to the template.
            self.env.add_to_compute(self._fields["signature"], enforced)
        return users

    def write(self, vals):
        if not self or (
            "signature" not in vals
            and not self.env["res.company"]
            .sudo()
            .search_count([("company_signature_enforced", "=", True)], limit=1)
        ):
            # Nothing can change state without an enforced company, except a
            # signature write (which resets the "generated" flag).
            return super().write(vals)
        # Transitions are keyed on the real before/after enforced state (not on
        # the keys of vals): ``share`` is computed from the groups, and
        # archived users must be covered too.
        users = self.with_context(active_test=False)
        with users._company_signature_transition():
            result = super().write(vals)
        if "signature" in vals:
            enforced_after = users._company_signature_enforced_users()
            # A person wrote it: it is personal again (when not enforced).
            (users - enforced_after).sudo().signature_is_generated = False
            # An enforced user cannot persist a divergent signature.
            self.env.add_to_compute(self._fields["signature"], enforced_after)
        return result

    def action_restore_personal_signature(self):
        for user in self:
            if user._is_company_signature_enforced():
                raise UserError(
                    _(
                        "%s is still subject to the company-standard "
                        "signature. Disable the policy first.",
                        user.name,
                    )
                )
        for user in self:
            backup = user.sudo().personal_signature_backup
            if backup:
                user.signature = backup
        return True
