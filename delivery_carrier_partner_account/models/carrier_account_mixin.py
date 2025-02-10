from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


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
    carrier_id = fields.Many2one(
        comodel_name="delivery.carrier",
        string="Carrier",
        compute="_compute_carrier_id",
        store=True,
        inverse="_on_carrier_fields_changed",
        compute_sudo=True,
    )

    _default_carrier_field = "property_delivery_carrier_id"
    _default_carrier_account_field = "default_carrier_account_id"

    delivery_billing_mode = fields.Selection(
        [
            ("no charge", "No Charge"),
            ("ppc", "Prepaid & Charge"),
            ("prepaid", "Prepaid"),
            ("collect", "Collect"),
            ("third party", "Third Party"),
        ],
        help=(
            """
        Prepaid: The shipper will pay the carrier and the client pays the estimate.
        Prepaid & Charge: The shipper will pay the carrier and bill the client based on the actual price paid.
        Collect: The recipient will be billed (account information needed)
        Third Party: A third party will be billed (account information needed)
        """
        ),
        string="Delivery Billing Mode",
        compute="_compute_delivery_billing_mode",
        inverse="_on_carrier_fields_changed",
        store=True,
        compute_sudo=True,
    )

    carrier_account_id = fields.Many2one(
        comodel_name="delivery.carrier.account",
        ondelete="restrict",
        string="Carrier Account",
        compute="_compute_carrier_account_id",
        inverse="_on_carrier_fields_changed",
        store=True,
        compute_sudo=True,
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

    valid_carrier_ids = fields.One2many(
        comodel_name="delivery.carrier",
        compute="_compute_valid_carrier_ids",
        compute_sudo=True,
    )

    def _on_carrier_fields_changed(self):
        """Hook for subclasses to perform additional actions when carrier fields change."""
        pass

    @api.depends(
        "valid_carrier_ids",
        "sender_id",
        "recipient_id",
        "delivery_billing_mode",
    )
    def _compute_carrier_id(self):
        for rec in self.filtered(
            lambda rec: not rec.carrier_id
            or rec.carrier_id not in rec.valid_carrier_ids
        ):
            rec.carrier_id = rec._get_default_carrier()

    def _get_default_carrier(self):
        self.ensure_one()
        recipient = self.recipient_id
        sender = self.sender_id
        def_car = self._default_carrier_field
        match self.delivery_billing_mode:
            case "collect":
                return getattr(recipient, def_car) or getattr(
                    recipient.commercial_partner_id, def_car
                )
            case "ppc" | "prepaid" | "no charge":
                return getattr(sender, def_car) or getattr(
                    sender.commercial_partner_id, def_car
                )
            case _:
                return False

    @api.depends(
        "sender_id",
        "recipient_id",
        "delivery_billing_mode",
        "carrier_id",
        "valid_carrier_account_ids",
    )
    def _compute_carrier_account_id(self):
        for rec in self.filtered(
            lambda rec: not rec.carrier_account_id
            or rec.carrier_account_id not in rec.valid_carrier_account_ids
        ):
            rec.carrier_account_id = rec._get_default_carrier_account()

    def _get_default_carrier_account(self):
        self.ensure_one()
        match self.delivery_billing_mode:
            case "collect":
                default_acct = getattr(
                    self.recipient_id, self._default_carrier_account_field
                ) or getattr(
                    self.recipient_id.commercial_partner_id,
                    self._default_carrier_account_field,
                )
                if default_acct and default_acct.delivery_carrier_id == self.carrier_id:
                    return default_acct
                return self.recipient_id.get_carrier_account(self.carrier_id)
            case "ppc" | "prepaid" | "no charge":
                default_acct = getattr(
                    self.sender_id, self._default_carrier_account_field
                ) or getattr(
                    self.sender_id.commercial_partner_id,
                    self._default_carrier_account_field,
                )
                if default_acct and default_acct.delivery_carrier_id == self.carrier_id:
                    return default_acct
                return self.sender_id.get_carrier_account(self.carrier_id)
            case _:
                return False

    @api.depends("carrier_account_id")
    def _compute_delivery_billing_mode(self):
        for rec in self.filtered(lambda rec: not rec.delivery_billing_mode):
            if not rec.carrier_account_id:
                rec.delivery_billing_mode = False
                continue
            account_partner = rec.carrier_account_id.partner_id
            if account_partner in (
                rec.recipient_id | rec.recipient_id.commercial_partner_id
            ):
                rec.delivery_billing_mode = "collect"
            elif account_partner in (
                rec.sender_id | rec.sender_id.commercial_partner_id
            ):
                rec.delivery_billing_mode = "ppc"
            else:
                rec.delivery_billing_mode = "third party"

    @api.depends(
        "delivery_billing_mode",
        "carrier_id",
        "recipient_id",
        "sender_id",
        "carrier_account_id",
    )
    def _compute_valid_carrier_account_ids(self):
        for rec in self:
            match rec.delivery_billing_mode:
                case "collect":
                    rec.valid_carrier_account_ids = (
                        (rec.recipient_id | rec.recipient_id.commercial_partner_id)
                        .mapped("carrier_account_ids")
                        .filtered(
                            lambda account: account.delivery_carrier_id
                            == rec.carrier_id
                        )
                    )
                case "third party":
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
                                    rec.sender_id.commercial_partner_id.id,
                                    rec.recipient_id.id,
                                    rec.recipient_id.commercial_partner_id.id,
                                ],
                            ),
                        ]
                    )
                case "prepaid" | "ppc" | "no charge":
                    rec.valid_carrier_account_ids = (
                        (rec.sender_id | rec.sender_id.commercial_partner_id)
                        .mapped("carrier_account_ids")
                        .filtered(
                            lambda account: account.delivery_carrier_id
                            == rec.carrier_id
                        )
                    )
                case _:
                    rec.valid_carrier_account_ids = self.env[
                        "delivery.carrier.account"
                    ].search([])

    @api.depends("valid_carrier_account_ids")
    def _compute_valid_carrier_ids(self):
        for rec in self:
            rec.valid_carrier_ids = rec.valid_carrier_account_ids.mapped(
                "delivery_carrier_id"
            )

    def _on_carrier_fields_changed(self):
        pass

    @api.constrains("delivery_billing_mode", "carrier_id", "carrier_account_id")
    def _check_carrier_account(self):
        for rec in self:
            if rec.carrier_account_id and rec.delivery_billing_mode:
                if (
                    rec.delivery_billing_mode == "collect"
                    and rec.carrier_account_id
                    not in (
                        rec.recipient_id | rec.recipient_id.commercial_partner_id
                    ).carrier_account_ids
                ):
                    raise UserError(
                        "Carrier account is not associated with the recipient, but billing mode is collect."
                    )
                elif (
                    rec.delivery_billing_mode in ["prepaid", "ppc", "no charge"]
                    and rec.carrier_account_id
                    not in (
                        rec.sender_id | rec.sender_id.commercial_partner_id
                    ).carrier_account_ids
                ):
                    raise UserError(
                        "Carrier account is not associated with the sender, but billing mode is prepaid, ppc or no charge."
                    )
                elif (
                    rec.delivery_billing_mode == "third party"
                    and rec.carrier_account_id
                    in (
                        rec.sender_id
                        | rec.sender_id.commercial_partner_id
                        | rec.recipient_id
                        | rec.recipient_id.commercial_partner_id
                    ).carrier_account_ids
                ):
                    raise UserError(
                        "Third party carrier account cannot belong to sender or recipient."
                    )
