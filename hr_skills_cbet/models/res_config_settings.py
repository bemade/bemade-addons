from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Company-level CBET policy defaults. Per-competency fields seed from these
    # (UC-CAT-07 AC1, UC-EVL-06 AC4, UC-VAL-01 AC1).
    cbet_default_validity_months = fields.Integer(
        string="Default certification validity (months)", default=24,
    )
    cbet_reprise_deadline_days = fields.Integer(
        string="Default reprise-completion deadline (days)", default=30,
    )
    cbet_expiry_horizon_months = fields.Integer(
        string="Certification expiry warning horizon (months)", default=3,
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cbet_default_validity_months = fields.Integer(
        related="company_id.cbet_default_validity_months", readonly=False,
    )
    cbet_reprise_deadline_days = fields.Integer(
        related="company_id.cbet_reprise_deadline_days", readonly=False,
    )
    cbet_expiry_horizon_months = fields.Integer(
        related="company_id.cbet_expiry_horizon_months", readonly=False,
    )
