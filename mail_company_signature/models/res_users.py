from contextlib import contextmanager

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import email_normalize


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
    # Self-service toggle, same pattern as hr's own employee fields on the user
    # (registered in SELF_READABLE/WRITEABLE_FIELDS below).
    signature_show_mobile = fields.Boolean(
        related="employee_id.signature_show_mobile",
        readonly=False,
        related_sudo=False,
    )
    mail_send_as_alias_id = fields.Many2one(
        "mail.alias",
        string="Sending address",
        domain="[('alias_name', '!=', False), ('alias_domain_id', '!=', False)]",
        ondelete="set null",
        copy=False,
        help="Team inbox this user's emails show instead of their personal "
        "address: the {{work_email}} placeholder of the company signature "
        "prints it. When the company setting \"Send from the signature "
        "address\" is on, the emails also go out from it (\"Name (Team)\" "
        "<inbox>) with replies to it. A document can impose its own address "
        "(a helpdesk ticket: its team's), and so can a template with a fixed "
        "sender (purchasing@).",
    )
    signature_is_generated = fields.Boolean(
        groups="base.group_system",
        copy=False,
        default=False,
        help="Set when the current signature was produced by the company "
        "template rather than written by a person.",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        # company_signature_enforced sits (invisible) on the preferences form.
        # A form field missing from this list makes res.users.read() drop its
        # self-read sudo, so a non-HR user's My Preferences then fails on hr's
        # private employee fields (pin, private_street, ...).
        return super().SELF_READABLE_FIELDS + [
            "company_signature_enforced",
            "signature_show_mobile",
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["signature_show_mobile"]

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
        "employee_ids.signature_show_mobile",
        "employee_ids.work_email",
        "mail_send_as_alias_id",
        "mail_send_as_alias_id.alias_full_name",
    )
    def _compute_signature(self):
        enforced = self._company_signature_enforced_users()
        super(ResUsers, self - enforced)._compute_signature()
        if not enforced:
            return
        values_by_user = enforced.sudo()._company_signature_values()
        for user in enforced:
            company = user.company_id.sudo()
            user.signature = company._company_signature_compact(
                company._company_signature_render(values_by_user[user.id])
            )

    @api.onchange("signature_show_mobile")
    def _onchange_signature_show_mobile(self):
        """Refresh the signature preview in the form before saving.

        The stored signature is regenerated on save; this only renders what
        it will become, from the saved employee data and the box as ticked
        in the form.
        """
        for user in self:
            origin = user._origin
            if not origin or origin not in origin._company_signature_enforced_users():
                continue
            values = origin.sudo()._company_signature_values()[origin.id]
            emp = origin.sudo()._company_signature_employees().get(origin.id)
            values["mobile_phone"] = (
                (emp.mobile_phone or "") if emp and user.signature_show_mobile else ""
            )
            company = origin.company_id.sudo()
            user.signature = company._company_signature_compact(
                company._company_signature_render(values)
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
                "mobile_phone": (
                    emp.mobile_phone if emp and emp.signature_show_mobile else ""
                )
                or "",
                "work_email": user.mail_send_as_alias_id.alias_full_name
                or (emp.work_email if emp else "")
                or user.email
                or "",
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
    # Sending address (signature, and From when the company asks for it)
    # ------------------------------------------------------------------
    def _mail_personal_emails(self):
        """The user's personal addresses, normalized: email, login (when it is
        an address) and employee work emails."""
        self.ensure_one()
        user = self.sudo()
        employees = (
            self.env["hr.employee"]
            .sudo()
            .with_context(active_test=False)
            .search([("user_id", "=", user.id)])
        )
        candidates = [user.email, user.login, *employees.mapped("work_email")]
        return {email for email in map(email_normalize, filter(None, candidates)) if email}

    def _mail_sender_info(self, record=None, email_from=None):
        """The address this user sends from (and shows in the signature) on an
        email about ``record``, sent with a template whose sender is
        ``email_from``. Pure, no write.

        In priority:

        a. the record's override (``mail.thread._mail_sender_override``, e.g.
           a helpdesk ticket: its team's address);
        b. the template's fixed sender (``email_from`` or the context key
           ``mail_signature_email_from``) when it is not personal (a
           purchasing@ template);
        c. the user's "Sending address" (``mail_send_as_alias_id``);
        d. the user's own address (employee work email, else user email).

        Portal users always get d.

        :return: dict ``email`` (address as shown), ``label`` (team name shown
            after the person's name in From, may be empty), ``personal``
            (True for d), ``source`` (``record``, ``template``, ``user``,
            ``personal``)
        """
        self.ensure_one()
        user = self.sudo()
        if not user.share:
            if record is not None and len(record) == 1 and hasattr(record, "_mail_sender_override"):
                override = record._mail_sender_override(user)
                if override and email_normalize(override.get("email") or ""):
                    return {
                        "email": email_normalize(override["email"]),
                        "label": override.get("label") or "",
                        "personal": False,
                        "source": "record",
                    }
            fixed = email_from or self.env.context.get("mail_signature_email_from")
            fixed = email_normalize(fixed or "") if fixed and "{" not in fixed else False
            if fixed and fixed not in user._mail_personal_emails():
                return {"email": fixed, "label": "", "personal": False, "source": "template"}
            alias = user.mail_send_as_alias_id
            alias_email = email_normalize(alias.alias_full_name or "") if alias else False
            if alias_email:
                return {
                    "email": alias_email,
                    "label": alias._mail_send_as_label(),
                    "personal": False,
                    "source": "user",
                }
        emp = user._company_signature_employees().get(user.id)
        return {
            "email": (emp.work_email if emp else "") or user.email or "",
            "label": "",
            "personal": True,
            "source": "personal",
        }

    def _mail_sender_address(self, record=None, email_from=None):
        """See ``_mail_sender_info``: the address only."""
        return self._mail_sender_info(record, email_from)["email"]

    def _mail_signature_for(self, record=None, email_from=None):
        """The signature this user's email about ``record`` carries.

        Users under the company signature policy: the company template
        rendered with ``{{work_email}}`` = the sending address for this
        context (the same render as the stored signature, which is the
        context-free one). Other users: their stored signature, unchanged.
        """
        self.ensure_one()
        user = self.sudo()
        signature = user.signature
        if user not in user._company_signature_enforced_users():
            return signature
        address = user._mail_sender_address(record, email_from)
        # The stored signature is the context-free one (no record, no
        # template sender, whatever the context carries).
        if address == user.with_context(mail_signature_email_from=False)._mail_sender_address():
            return signature
        values = user._company_signature_values()[user.id]
        values["work_email"] = address
        company = user.company_id
        return company._company_signature_compact(company._company_signature_render(values))

    @api.model
    def _mail_signature_swap_printed(self, html, users, record=None, email_from=None):
        """``html`` (a rendered template) with each verbatim copy of a stored
        signature of ``users`` replaced by that user's signature for this
        context (``_mail_signature_for``). Only the signature fragments
        change."""
        if not html:
            return html
        result = str(html)
        for user in users.sudo():
            stored = str(user.signature or "")
            if not stored or stored not in result:
                continue
            built = str(user._mail_signature_for(record, email_from) or "")
            if built != stored:
                result = result.replace(stored, built)
        if result == str(html):
            return html
        return Markup(result) if isinstance(html, Markup) else result
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
