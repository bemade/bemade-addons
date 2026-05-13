from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    owned_organizational_unit_ids = fields.One2many(
        "organizational.unit",
        "owner_id",
        string="Owned Customer Accounts",
        help="Organizational units (customer accounts) owned by this partner.",
    )
    organizational_unit_ids = fields.Many2many(
        "organizational.unit",
        string="Member Of Accounts",
        help="Organizational units this partner is an explicit member of.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner in partners:
            if partner.is_company and not partner.parent_id:
                self.env["organizational.unit"].sudo().create({
                    "name": partner.name,
                    "owner_id": partner.id,
                })
        return partners

    def write(self, vals):
        # Capture old names before write so we can detect which OUs were in sync
        old_names = {}
        if "name" in vals:
            for partner in self:
                old_names[partner.id] = partner.name
        res = super().write(vals)
        if "name" in vals:
            for partner in self:
                for ou in partner.owned_organizational_unit_ids:
                    if ou.name == old_names.get(partner.id):
                        ou.sudo().write({"name": partner.name})
        return res

    def action_view_organizational_unit(self):
        """Navigate to the partner's organizational unit."""
        self.ensure_one()
        ou = self.owned_organizational_unit_ids[:1] or self.organizational_unit_ids[:1]
        if not ou:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "res_model": "organizational.unit",
            "res_id": ou.id,
            "view_mode": "form",
            "target": "current",
        }
