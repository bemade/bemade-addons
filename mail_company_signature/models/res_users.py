from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = "res.users"

    # groups=False is deliberate: a related field copies the groups of its
    # target (base.group_system), which would make the flag unreadable for
    # plain internal users and break the readonly modifier on the signature in
    # My Preferences. The value is a harmless boolean.
    company_signature_enforced = fields.Boolean(
        related="company_id.company_signature_enforced",
        groups=False,
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

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def _is_company_signature_enforced(self):
        self.ensure_one()
        return not self.share and bool(
            self.company_id.sudo().company_signature_enforced
        )

    def _company_signature_enforced_users(self):
        return self.filtered(lambda u: u._is_company_signature_enforced())

    @api.depends(
        "name",
        "email",
        "share",
        "company_id",
        "company_id.company_signature_enforced",
        "company_id.company_signature_template",
        "company_id.name",
        "company_id.phone",
        "company_id.email",
        "company_id.website",
        "employee_ids",
        "employee_ids.active",
        "employee_ids.company_id",
        "employee_ids.name",
        "employee_ids.job_title",
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

        Does not use ``employee_ids`` (its domain depends on ``env.company``);
        only an employee of the user's own company counts.
        """
        employees = self.env["hr.employee"].sudo().search(
            [
                ("user_id", "in", self.ids),
                ("company_id", "in", self.company_id.ids),
            ],
            order="id",
        )
        emp_by_key = {}
        for emp in employees:
            emp_by_key.setdefault((emp.user_id.id, emp.company_id.id), emp)
        result = {}
        for user in self:
            emp = emp_by_key.get((user.id, user.company_id.id))
            company = user.company_id
            result[user.id] = {
                "name": (emp.name if emp else "") or user.name or "",
                "job_title": (emp.job_title if emp else "") or "",
                "work_phone": (emp.work_phone if emp else "") or "",
                "mobile_phone": (emp.mobile_phone if emp else "") or "",
                "work_email": (emp.work_email if emp else "") or user.email or "",
                "company_name": company.name or "",
                "company_phone": company.phone or "",
                "company_email": company.email or "",
                "company_website": company.website or "",
            }
        return result

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
        enforced_before = users._company_signature_enforced_users()
        prior = {
            user.id: user.signature
            for user in (users - enforced_before)
            if not user.sudo().signature_is_generated
        }
        result = super().write(vals)
        enforced_after = users._company_signature_enforced_users()
        newly = enforced_after - enforced_before
        for user in newly:
            if user.id in prior:
                user.sudo().personal_signature_backup = prior[user.id]
        released = enforced_before - enforced_after
        if released:
            released.sudo().signature_is_generated = True
        if "signature" in vals:
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
