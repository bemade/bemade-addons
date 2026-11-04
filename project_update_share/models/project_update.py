# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import Command, api, fields, models
from odoo.tools import format_date

# Writes that can share an update with someone new.
_SHARING_FIELDS = {"internal_only", "recipient_ids", "project_id"}


class ProjectUpdate(models.Model):
    _inherit = "project.update"

    internal_only = fields.Boolean(
        default=True,
        help="Untick to share this update with its recipients: each is "
        "emailed once, and can read it on the portal.",
    )
    recipient_ids = fields.Many2many(
        "res.partner",
        "project_update_share_recipient_rel",
        "update_id",
        "partner_id",
        string="Recipients",
        compute="_compute_recipient_ids",
        store=True,
        readonly=False,
        help="Who receives this update by email and can read it on the "
        "portal. Prefilled with the project's followers and collaborators.",
    )
    emailed_partner_ids = fields.Many2many(
        "res.partner",
        "project_update_share_emailed_rel",
        "update_id",
        "partner_id",
        string="Already Emailed",
        readonly=True,
        copy=False,
    )

    @api.depends("internal_only", "project_id")
    def _compute_recipient_ids(self):
        for update in self:
            if update.internal_only or update.recipient_ids or not update.project_id:
                update.recipient_ids = update.recipient_ids
            else:
                update.recipient_ids = update.project_id._update_share_default_recipients()

    @api.model_create_multi
    def create(self, vals_list):
        updates = super().create(vals_list)
        updates._share_email_new_recipients()
        return updates

    def write(self, vals):
        res = super().write(vals)
        if _SHARING_FIELDS & set(vals):
            self._share_email_new_recipients()
        return res

    def _share_email_new_recipients(self):
        """Email every recipient of a shared update who was never emailed it."""
        for update in self.filtered(lambda u: not u.internal_only):
            new = update.recipient_ids - update.emailed_partner_ids
            if not new:
                continue
            update._share_post(new)
            update.emailed_partner_ids = [Command.link(p.id) for p in new]

    def _share_post(self, partners):
        self.ensure_one()
        project = self.project_id
        lang = project.partner_id.lang or self.env.lang
        update = self.with_context(lang=lang)
        statuses = dict(update._fields["status"]._description_selection(update.env))
        body = update.env["ir.qweb"]._render(
            "project_update_share.update_share_message",
            {
                "update": update,
                "status_label": statuses.get(update.status, ""),
                "date_label": format_date(update.env, update.date, lang_code=lang),
                "url": project._update_share_portal_url(),
            },
        )
        update.message_post(
            body=body,
            partner_ids=partners.ids,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
