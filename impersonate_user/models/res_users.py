from odoo import models, fields, _, api
from odoo.exceptions import AccessError
from odoo.http import request


class ResUsers(models.Model):
    _inherit = "res.users"

    is_impersonated = fields.Boolean(
        compute="_compute_is_impersonated",
    )

    def impersonate_user(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can impersonate users."))
        request.session["original_uid"] = request.uid
        request.session.uid = self.id
        return {
            "type": "ir.actions.act_url",
            "url": self.env["ir.config_parameter"].get_param("web.base.url") + "/web",
            "target": "self",
        }

    @api.model
    def unimpersonate(self):
        original_uid = request.session.pop("original_uid", False)
        if original_uid:
            request.session.uid = original_uid
            return {
                "type": "ir.actions.act_url",
                "url": self.env["ir.config_parameter"].get_param("web.base.url")
                + "/web",
                "target": "self",
            }
        else:
            raise AccessError(_("This user is not impersonated."))

    def _compute_is_impersonated(self):
        original_uid = request.session.get("original_uid", False)
        if not original_uid:
            self.write({"is_impersonated": False})
        else:
            for rec in self:
                rec.is_impersonated = rec.id == request.session.uid
