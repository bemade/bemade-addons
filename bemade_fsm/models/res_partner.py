from odoo import api, fields, models


def _normalize_site_note(note):
    """An empty or blank site note is no note."""
    return (note or "").strip() and note or False


class Partner(models.Model):
    _inherit = "res.partner"

    is_site_contact = fields.Boolean(
        string="Is a site contact",
        compute="_compute_is_site_contact",
        search="_search_is_site_contact",
    )

    is_service_site = fields.Boolean(
        help="A partner is a service site if they have one or more equipments, "
        "site contacts or work order contacts."
    )

    site_ids = fields.Many2many(
        string="Work Sites",
        comodel_name="res.partner",
        relation="res_partner_site_contact_rel",
        column1="site_contact_id",
        column2="site_id",
        tracking=True,
        domain=[("is_service_site", "=", True)],
    )

    site_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="res_partner_site_contact_rel",
        column1="site_id",
        column2="site_contact_id",
        domain=[("is_service_site", "=", False)],
        tracking=True,
    )

    work_order_contacts = fields.Many2many(
        string="Work Order Recipients",
        comodel_name="res.partner",
        relation="res_partner_work_order_contacts_rel",
        column1="res_partner_id",
        column2="work_order_contact_id",
        domain=[("is_service_site", "=", False)],
        tracking=True,
    )

    fsm_site_note = fields.Text(
        string="Site note",
        tracking=True,
        help="Shown as a banner at the top of every field service task at this "
        "site (the task's customer / delivery address) until someone clears it. "
        "A note on the parent company does not show on its delivery addresses.",
    )

    fsm_site_note_history_ids = fields.One2many(
        "fsm.site.note.history",
        "partner_id",
        string="Site note history",
        readonly=True,
    )


    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners.filtered("fsm_site_note")._log_fsm_site_note_history()
        return partners

    def write(self, vals):
        if "fsm_site_note" not in vals:
            return super().write(vals)
        before = {
            partner.id: _normalize_site_note(partner.fsm_site_note)
            for partner in self.sudo()
        }
        result = super().write(vals)
        self.filtered(
            lambda p: _normalize_site_note(p.fsm_site_note) != before[p.id]
        )._log_fsm_site_note_history()
        return result

    def _log_fsm_site_note_history(self):
        """One ``fsm.site.note.history`` row per partner, with its current note.

        The visit the note was edited from, if any, comes from the
        ``fsm_site_note_task_id`` context key. Created with sudo: the history
        is read-only for every group. ``sudo()`` keeps the uid, so the author
        stays the user who made the change."""
        if not self:
            return self.env["fsm.site.note.history"]
        task_id = self.env.context.get("fsm_site_note_task_id") or False
        return (
            self.env["fsm.site.note.history"]
            .sudo()
            .create(
                [
                    {
                        "partner_id": partner.id,
                        "content": _normalize_site_note(partner.fsm_site_note),
                        "author_id": self.env.uid,
                        "task_id": task_id,
                    }
                    for partner in self
                ]
            )
        )


    @api.depends("site_ids")
    def _compute_is_site_contact(self):
        for rec in self:
            rec.is_site_contact = rec.site_ids

    @api.model
    def _search_is_site_contact(self, operator, value):
        return [("site_ids", "!=", False)]

    @api.depends("equipment_ids", "site_contacts", "work_order_contacts")
    def _compute_is_service_site(self):
        for rec in self:
            rec.is_service_site = (
                rec.equipment_ids or rec.site_contacts or rec.work_order_contacts
            )
