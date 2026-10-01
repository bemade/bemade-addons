from odoo import api, fields, models, tools


class MailNotificationScope(models.Model):
    """One row per model opted into scoped notifications.

    A model listed here (and active) only ever produces in-app
    notifications for internal users: externals, portal users and bare
    email recipients are never notified, and internal users who prefer
    email get an inbox notification instead. See ``mail.thread``.
    """

    _name = "mail.notification.scope"
    _description = "Notification Scope Rule"
    _rec_name = "model_id"

    model_id = fields.Many2one(
        "ir.model",
        required=True,
        ondelete="cascade",
        index=True,
        domain=[
            ("is_mail_thread", "=", True),
            ("transient", "=", False),
            ("model", "!=", "discuss.channel"),
        ],
    )
    model = fields.Char(
        string="Model Name", related="model_id.model", store=True, readonly=True
    )
    active = fields.Boolean(default=True)

    _model_uniq = models.Constraint(
        "UNIQUE(model_id)", "This model is already in the notification scope."
    )

    @api.model
    @tools.ormcache()
    def _get_scoped_model_names(self):
        rules = self.sudo().with_context(active_test=True).search([])
        return frozenset(rules.mapped("model"))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env.registry.clear_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache()
        return result
