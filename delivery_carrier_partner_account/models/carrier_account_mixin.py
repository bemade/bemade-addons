from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CarrierAccountMixin(models.AbstractModel):
    """
    Carrier Account Mixin.

    This class provides functionality for handling carrier accounts within an order
    system. It ensures that the correct carrier account is used based on the
    delivery billing mode (collect, third party, prepaid). It also provides methods
    to compute and validate carrier accounts according to the selected carrier and
    partners involved in the order.

    Most implementations should override the sender_id and recipient_id fields with
    related fields that simply point to the res.partner record that is appropriate. For
    example, the sender_id for a sales order would be company_id.partner_id and its
    recipient_id would be partner_id.
    """

    _name = "carrier.account.mixin"
    _description = "Carrier Account Mixin"

    sender_id = fields.Many2one(comodel_name="res.partner", string="Sender")
    recipient_id = fields.Many2one(comodel_name="res.partner", string="Recipient")
    carrier_id = fields.Many2one(comodel_name="delivery.carrier", string="Carrier")

    delivery_billing_mode = fields.Selection(
        [
            ("no charge", "No Charge"),
            ("ppc", "Prepaid & Charge"),
            ("prepaid", "Prepaid"),
            ("collect", "Collect"),
            ("third party", "Third Party"),
        ],
        help=_(
            """
        Prepaid: The shipper will pay the carrier and the client pays the estimate.
        Prepaid & Charge: The shipper will pay the carrier and bill the client based on the actual price paid.
        Collect: The recipient will be billed (account information needed)
        Third Party: A third party will be billed (account information needed)
        """
        ),
        string="Delivery Billing Mode",
    )

    carrier_account_id = fields.Many2one(
        comodel_name="delivery.carrier.account",
        ondelete="restrict",
        compute="_compute_carrier_account_id",
        inverse="_inverse_carrier_account_id",
        store=True,
        compute_sudo=True,
        string="Carrier Account",
    )

    carrier_account_owner_id = fields.Many2one(
        comodel_name="res.partner",
        related="carrier_account_id.partner_id",
        string="Carrier Account Owner",
    )

    valid_carrier_account_ids = fields.One2many(
        comodel_name="delivery.carrier.account",
        compute="_compute_valid_carrier_account_ids",
        compute_sudo=True,
        string="Valid Carrier Accounts",
    )

    @api.depends("delivery_billing_mode", "carrier_id", "recipient_id", "sender_id")
    def _compute_valid_carrier_account_ids(self):
        for rec in self:
            if rec.delivery_billing_mode == "collect":
                rec.valid_carrier_account_ids = (
                    (rec.recipient_id | rec.recipient_id.commercial_partner_id)
                    .mapped("carrier_account_ids")
                    .filtered(
                        lambda account: account.delivery_carrier_id == rec.carrier_id
                    )
                )
            if rec.delivery_billing_mode == "third party":
                rec.valid_carrier_account_ids = self.env[
                    "delivery.carrier.account"
                ].search(
                    [
                        ("delivery_carrier_id", "=", rec.carrier_id.id),
                        (
                            "partner_id",
                            "not in",
                            [
                                rec.sender_id.id,
                                rec.recipient_id.id,
                                rec.recipient_id.commercial_partner_id.id,
                            ],
                        ),
                    ]
                )
            if rec.delivery_billing_mode in ["prepaid", "ppc"]:
                rec.valid_carrier_account_ids = (
                    rec.sender_id.carrier_account_ids.filtered(
                        lambda account: account.delivery_carrier_id == rec.carrier_id
                    )
                )
            if rec.delivery_billing_mode == "no charge":
                rec.valid_carrier_account_ids = self.env["delivery.carrier.account"]
            if not rec.delivery_billing_mode:
                rec.valid_carrier_account_ids = self.env["delivery.carrier.account"]

    @api.depends("delivery_billing_mode", "carrier_id", "valid_carrier_account_ids")
    def _compute_carrier_account_id(self):
        """Compute the carrier account to use for this record if one is not set or if
        the current one doesn't match the carrier_id selected.

        When delivery_billing_mode is collect, we need to choose a carrier account that
        matches both the carrier_id and the partner_id or its commercial partner.

        When it is third party, any account matching the carrier_id is fine.

        When it is prepaid or ppc, we select the company's account.
        """
        for rec in self:
            if rec.delivery_billing_mode == "collect":
                if rec.carrier_account_id not in rec.valid_carrier_account_ids:
                    if (
                        rec.recipient_id.default_carrier_account_id.delivery_carrier_id
                        == rec.carrier_id
                    ):
                        rec.carrier_account_id = (
                            rec.recipient_id.default_carrier_account_id
                        )
                    elif rec.valid_carrier_account_ids:
                        rec.carrier_account_id = rec.valid_carrier_account_ids[0]
                    else:
                        raise UserError(
                            "The client does not have an account with the selected carrier."
                        )
            if rec.delivery_billing_mode == "third party":
                if rec.carrier_account_id not in rec.valid_carrier_account_ids:
                    rec.carrier_account_id = False
            if rec.delivery_billing_mode in ["prepaid", "ppc"]:
                rec.carrier_account_id = (
                    self.env["delivery.carrier.account"]
                    .search([("partner_id", "=", rec.sender_id.id)])
                    .filtered(
                        lambda account: account.delivery_carrier_id == rec.carrier_id
                    )
                )
            if (
                rec.delivery_billing_mode == "no charge"
                or not rec.delivery_billing_mode
            ):
                rec.carrier_account_id = False

    @api.constrains("carrier_account_id")
    def _check_account_id(self):
        for rec in self:
            if (
                not rec.delivery_billing_mode
                or rec.delivery_billing_mode == "no charge"
            ):
                if rec.carrier_account_id:
                    raise UserError(
                        _("No carrier account should be set for no charge delivery.")
                    )
                continue
            # We allow empty carrier account for third party since we can't always
            # set it automatically.
            if (
                rec.delivery_billing_mode == "third party"
                and not rec.carrier_account_id
            ):
                continue
            if rec.carrier_account_id not in rec.valid_carrier_account_ids:
                raise UserError(_("Invalid carrier account selected."))

    def _inverse_carrier_account_id(self):
        pass
