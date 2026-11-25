from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Documents a contact may come from, most telling first. Only the models
# installed in the database are looked at.
ORIGIN_MODELS = ("crm.lead", "helpdesk.ticket", "sale.order")


class PartnerParentSuggestion(models.Model):
    _name = "partner.parent.suggestion"
    _description = "Unassigned Contact (company to choose)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "partner_id"

    partner_id = fields.Many2one(
        "res.partner", string="Contact", required=True, ondelete="cascade", index=True, readonly=True
    )
    partner_email = fields.Char(related="partner_id.email", string="Email")
    partner_create_uid = fields.Many2one(related="partner_id.create_uid", string="Contact created by")
    partner_create_date = fields.Datetime(related="partner_id.create_date", string="Contact created on")
    candidate_ids = fields.Many2many(
        "res.partner",
        "partner_parent_suggestion_candidate_rel",
        "suggestion_id",
        "partner_id",
        string="Candidate Companies",
        readonly=True,
    )
    chosen_parent_id = fields.Many2one(
        "res.partner",
        string="Company",
        domain="[('id', 'in', candidate_ids)]",
        help="Company to attach the contact to. Nothing is written until Apply assignments.",
    )
    email_domain = fields.Char(readonly=True)
    source = fields.Selection(
        [
            ("create", "Contact created"),
            ("email", "Email changed"),
            ("backfill", "Former division email"),
            ("suffix_fix", "Detached (domain suffix only)"),
        ],
        required=True,
        readonly=True,
    )
    origin = fields.Char(compute="_compute_origin")

    _partner_uniq = models.Constraint("UNIQUE(partner_id)", "A contact can only have one open row.")

    @api.constrains("chosen_parent_id", "candidate_ids")
    def _check_chosen_parent(self):
        for row in self:
            if row.chosen_parent_id and row.chosen_parent_id not in row.candidate_ids:
                raise ValidationError(self.env._("The chosen company must be one of the candidates."))

    def _compute_origin(self):
        models_ = [m for m in ORIGIN_MODELS if m in self.env]
        for row in self:
            row.origin = False
            for model in models_:
                record = self.env[model].sudo().search([("partner_id", "=", row.partner_id.id)], order="id", limit=1)
                if record:
                    row.origin = record.display_name
                    break

    @api.model
    def _queue(self, partner, candidates, email_domain, source):
        """Create or refresh the open row of ``partner``."""
        row = self.search([("partner_id", "=", partner.id)], limit=1)
        vals = {
            "candidate_ids": [fields.Command.set(candidates.ids)],
            "email_domain": email_domain,
            "source": source,
        }
        if row:
            if row.chosen_parent_id not in candidates:
                vals["chosen_parent_id"] = False
            row.write(vals)
            return row
        return self.create(dict(vals, partner_id=partner.id))

    def action_apply_assignments(self):
        """Attach every contact that received a choice; untouched rows stay."""
        rows = self or self.search([])
        rows = rows.filtered("chosen_parent_id")
        for row in rows:
            partner, company = row.partner_id, row.chosen_parent_id
            # Writing parent_id closes (deletes) the row.
            partner.write({"parent_id": company.id})
            partner._post_email_domain_note(
                Markup("Rattaché à %s depuis « Contacts non assignés ».<br/>Attached to %s from \"Unassigned contacts\".")
                % (company.display_name, company.display_name)
            )
        return {"type": "ir.actions.client", "tag": "soft_reload"}

    @api.model
    def _cron_remind_open_rows(self):
        """Weekly reminder: one To-Do for the configured user while rows are open."""
        user_id = int(
            self.env["ir.config_parameter"].sudo().get_param("bemade_partner_email_domain.reminder_user_id") or 0
        )
        user = self.env["res.users"].browse(user_id).exists()
        if not user:
            return
        count = self.search_count([])
        existing = self.env["mail.activity"].search(
            [("res_model", "=", self._name), ("user_id", "=", user.id), ("activity_type_id", "=", self.env.ref("mail.mail_activity_data_todo").id)]
        )
        if not count:
            return
        summary = "%(count)s contacts non assignés / %(count)s unassigned contacts" % {"count": count}
        if existing:
            existing[:1].summary = summary
            return
        oldest = self.search([], order="id", limit=1)
        oldest.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=user.id,
            summary=summary,
            note=Markup(
                "Des contacts attendent le choix de leur entreprise dans Contacts &gt; Contacts non assignés."
                "<br/>Contacts are waiting for their company in Contacts &gt; Unassigned contacts."
            ),
        )
