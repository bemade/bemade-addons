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
