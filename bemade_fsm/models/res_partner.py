from odoo import api, fields, models


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

    fsm_carried_todo_ids = fields.One2many(
        "fsm.carried.todo", "partner_id", string="Carried to-dos"
    )
    fsm_carried_todo_count = fields.Integer(
        string="To-dos for next visit",
        compute="_compute_fsm_carried_todo_count",
        help="To-dos noted at a visit's close that are not done yet.",
    )

    def _compute_fsm_carried_todo_count(self):
        groups = self.env["fsm.carried.todo"].sudo()._read_group(
            [("partner_id", "in", self.ids), ("state", "in", ("pending", "scheduled"))],
            ["partner_id"],
            ["__count"],
        )
        counts = {partner.id: count for partner, count in groups}
        for partner in self:
            partner.fsm_carried_todo_count = counts.get(partner.id, 0)

    def action_view_fsm_carried_todos(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "bemade_fsm.fsm_carried_todo_action"
        )
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = {
            "default_partner_id": self.id,
            "search_default_open": 1,
        }
        return action

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
