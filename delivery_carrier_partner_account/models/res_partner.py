from odoo import models, fields, api


class Partner(models.Model):
    _inherit = "res.partner"

    carrier_account_ids = fields.One2many(
        comodel_name="delivery.carrier.account",
        inverse_name="partner_id",
        tracking=2,
        string="Carrier Accounts",
    )

    default_carrier_account_id = fields.Many2one(
        comodel_name="delivery.carrier.account",
        tracking=1,
        ondelete="restrict",
    )

    def write(self, vals):
        update_default_carrier = (
            "carrier_account_ids" in vals and not self.default_carrier_account_id
        )
        res = super().write(vals)
        if update_default_carrier and self.carrier_account_ids:
            self.default_carrier_account_id = self.carrier_account_ids[0]
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            if not rec.default_carrier_account_id and rec.carrier_account_ids:
                rec.default_carrier_account_id = rec.carrier_account_ids[0]
        return res

    def get_carrier_account(self, carrier):
        self.ensure_one()
        own_accounts = self.carrier_account_ids.filtered(
            lambda account: account.delivery_carrier_id == carrier
        )
        if own_accounts:
            return own_accounts[0]
        commercial_patner_accounts = self.commercial_partner_id.carrier_account_ids.filtered(
            lambda account: account.delivery_carrier_id == carrier
        )
        if commercial_patner_accounts:
            return commercial_patner_accounts[0]
        return self.env["delivery.carrier.account"]