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
        compute="_compute_logistic_defaults",
        inverse="_inverse_default_carrier_account_id",
        store=True,
        tracking=1,
        ondelete="restrict",
    )

    property_delivery_carrier_id = fields.Many2one(
        compute="_compute_logistic_defaults",
        inverse="_inverse_property_delivery_carrier_id",
        store=True,
    )

    def _inverse_default_carrier_account_id(self):
        pass

    def _inverse_property_delivery_carrier_id(self):
        pass

    @api.depends(
        "carrier_account_ids",
        "carrier_account_ids.active",
        "carrier_account_ids.delivery_carrier_id",
    )
    def _compute_logistic_defaults(self):
        # Unset default carrier account if it is archived
        for partner in self.filtered(
            lambda partner: partner.default_carrier_account_id
            and not partner.default_carrier_account_id.active
        ):
            partner.default_carrier_account_id = False

        # Unset the default carrier if no accounts are available
        for partner in self.filtered(
            lambda partner: partner.property_delivery_carrier_id
        ).filtered(
            lambda partner: not partner.carrier_account_ids.filtered(
                lambda account: account.delivery_carrier_id
                == partner.property_delivery_carrier_id
                and account.active
            )
        ):
            partner.property_delivery_carrier_id = False

        # Set default carrier account if not set and accounts available
        for partner in self.filtered(
            lambda partner: not partner.default_carrier_account_id
            and partner.carrier_account_ids.filtered("active")
        ):
            partner.default_carrier_account_id = partner.carrier_account_ids.filtered(
                "active"
            )[0]

        # Set default carrier if not set and default account is set
        for partner in self.filtered(
            lambda partner: not partner.property_delivery_carrier_id
            and partner.default_carrier_account_id
        ):
            partner.property_delivery_carrier_id = (
                partner.default_carrier_account_id.delivery_carrier_id
            )

        # Reset default carrier if account is set and doesn't match
        for partner in self.filtered(
            lambda partner: partner.default_carrier_account_id
            and partner.default_carrier_account_id.delivery_carrier_id
            != partner.property_delivery_carrier_id
        ):
            partner.property_delivery_carrier_id = (
                partner.default_carrier_account_id.delivery_carrier_id
            )

    def get_carrier_account(self, carrier):
        self.ensure_one()
        own_accounts = self.carrier_account_ids.filtered(
            lambda account: account.delivery_carrier_id == carrier
        )
        if own_accounts:
            return own_accounts[0]
        commercial_patner_accounts = (
            self.commercial_partner_id.carrier_account_ids.filtered(
                lambda account: account.delivery_carrier_id == carrier
            )
        )
        if commercial_patner_accounts:
            return commercial_patner_accounts[0]
        return self.env["delivery.carrier.account"]

    def process_carrier_account_archiving(self):
        for partner in self:
            # Unset default carrier account if it is archived
            if (
                partner.default_carrier_account_id
                and not partner.default_carrier_account_id.active
            ):
                partner.default_carrier_account_id = False
            # Unset default carrier if not more accounts available
            if (
                partner.property_delivery_carrier_id
                and not partner.carrier_account_ids.filtered(
                    lambda account: account.delivery_carrier_id
                    == partner.property_delivery_carrier_id
                    and account.active
                )
            ):
                partner.property_delivery_carrier_id = False
