from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    application_ids = fields.One2many(
        "partner.application",
        "partner_id",
        string="Applications",
    )
    applications_count = fields.Integer(
        string="Applications Count",
        compute="_compute_applications_count",
    )
    application_type_ids = fields.One2many(
        comodel_name="partner.application.type",
        compute="_compute_application_type_ids",
        string="Application Types",
        readonly=True,
        search="_search_application_type_ids",
    )

    @api.depends("application_ids.application_type_id")
    def _compute_application_type_ids(self):
        for partner in self:
            partner.application_type_ids = partner.application_ids.mapped(
                "application_type_id"
            )

    def _search_application_type_ids(self, operator, value):
        return [("application_ids.application_type_id", operator, value)]

        @api.depends("application_ids")
        def _compute_applications_count(self):
            for partner in self:
                partner.applications_count = len(partner.application_ids)

    @api.depends("application_ids")
    def _compute_applications_count(self):
        for rec in self:
            rec.applications_count = len(rec.application_ids)
