from odoo import Command, api, fields, models

_SCOPE_MODEL_DOMAIN = [
    ("is_mail_thread", "=", True),
    ("transient", "=", False),
    ("model", "!=", "discuss.channel"),
]


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    notification_scope_all_models = fields.Boolean(
        string="Scope Notifications on All Models",
        config_parameter="mail_notification_scope.all_models",
        help="Apply scoped notifications to every model with a chatter.",
    )
    notification_scope_model_ids = fields.Many2many(
        "ir.model",
        "res_config_settings_notification_scope_model_rel",
        "settings_id",
        "model_id",
        string="Scoped Models",
        domain=_SCOPE_MODEL_DOMAIN,
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        rules = self.env["mail.notification.scope"].search([])
        res["notification_scope_model_ids"] = [Command.set(rules.model_id.ids)]
        return res

    def set_values(self):
        result = super().set_values()
        Rule = self.env["mail.notification.scope"]
        existing = Rule.with_context(active_test=False).search([])
        wanted = self.notification_scope_model_ids
        for rule in existing:
            should_be_active = rule.model_id in wanted
            if rule.active != should_be_active:
                rule.active = should_be_active
        missing = wanted - existing.model_id
        if missing:
            Rule.create([{"model_id": model.id} for model in missing])
        return result
