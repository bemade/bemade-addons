from odoo import Command, api, fields, models

_MODEL_DOMAIN = [
    ("is_mail_thread", "=", True),
    ("transient", "=", False),
    ("model", "!=", "discuss.channel"),
]


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    addressed_only_model_ids = fields.Many2many(
        "ir.model",
        "res_config_settings_addressed_only_model_rel",
        "settings_id",
        "model_id",
        string="Email Only When Addressed",
        domain=_MODEL_DOMAIN,
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        rules = self.env["mail.addressed.only.rule"].search([])
        res["addressed_only_model_ids"] = [Command.set(rules.model_id.ids)]
        return res

    def set_values(self):
        result = super().set_values()
        Rule = self.env["mail.addressed.only.rule"]
        existing = Rule.with_context(active_test=False).search([])
        wanted = self.addressed_only_model_ids
        for rule in existing:
            should_be_active = rule.model_id in wanted
            if rule.active != should_be_active:
                rule.active = should_be_active
        missing = wanted - existing.model_id
        if missing:
            Rule.create([{"model_id": model.id} for model in missing])
        return result
