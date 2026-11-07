from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    email_domain_suggest_only = fields.Boolean(
        string="Email domain: suggest only",
        config_parameter="bemade_partner_email_domain.suggest_only",
        help="When a single company matches the email domain of a new contact, queue it "
        "in Unassigned contacts instead of attaching it.",
    )
    email_domain_reminder_user_id = fields.Many2one(
        "res.users",
        string="Unassigned contacts reminder",
        config_parameter="bemade_partner_email_domain.reminder_user_id",
        domain="[('share', '=', False)]",
        help="Receives a weekly to-do while contacts wait in Unassigned contacts.",
    )
