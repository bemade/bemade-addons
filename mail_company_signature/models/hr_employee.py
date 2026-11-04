from odoo import api, models

# Employee fields deciding whether its user is subject to the policy.
POLICY_FIELDS = frozenset(("user_id", "company_id", "active"))


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _company_signature_policy_active(self):
        return bool(
            self.env["res.company"]
            .sudo()
            .search_count([("company_signature_enforced", "=", True)], limit=1)
        )

    @api.model_create_multi
    def create(self, vals_list):
        user_ids = [vals["user_id"] for vals in vals_list if vals.get("user_id")]
        if not user_ids or not self._company_signature_policy_active():
            return super().create(vals_list)
        users = self.env["res.users"].browse(user_ids)
        with users._company_signature_transition():
            return super().create(vals_list)

    def write(self, vals):
        if not POLICY_FIELDS.intersection(vals) or not (
            self._company_signature_policy_active()
        ):
            return super().write(vals)
        users = self.sudo().with_context(active_test=False).user_id
        if vals.get("user_id"):
            users |= self.env["res.users"].browse(vals["user_id"])
        with users._company_signature_transition():
            return super().write(vals)

    def unlink(self):
        if not self._company_signature_policy_active():
            return super().unlink()
        users = self.sudo().with_context(active_test=False).user_id
        with users._company_signature_transition():
            return super().unlink()
