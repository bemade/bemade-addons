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

    def _get_valid_carrier_partners(self):
        """Get partners that can have valid carrier accounts for the current billing mode.

        Returns:
            Tuple containing:
            - partners: recordset of partners that can have valid accounts
        """
        self.ensure_one()
        invalid_partners = self.env["res.partner"]

        match self.delivery_billing_mode:
            case "collect":
                return self.recipient_id | self.recipient_id.commercial_partner_id
            case "prepaid" | "ppc" | "no charge":
                return self.sender_id | self.sender_id.commercial_partner_id
            case "third party":
                invalid_partners = (
                    self.recipient_id | self.recipient_id.commercial_partner_id
                ) | (self.sender_id | self.sender_id.commercial_partner_id)
                return self.env["res.partner"].search(
                    [("id", "not in", invalid_partners.ids)]
                )
            case _:
                return self.env["res.partner"]

    @api.depends(
        "sender_id",
        "recipient_id",
        "delivery_billing_mode",
    )
    def _compute_carrier_id(self):
        for rec in self:
            if not rec.carrier_id:
                rec.carrier_id = rec._get_default_carrier()
            elif (
                rec.delivery_billing_mode
                and rec.carrier_id not in rec.valid_carrier_ids
                and not rec._has_valid_account_for_carrier()
            ):
                rec.carrier_id = rec._get_default_carrier()

    def _has_valid_account_for_carrier(self):
        """Check if there's a valid account for the current carrier and billing mode."""
        self.ensure_one()
        if not self.carrier_id or not self.delivery_billing_mode:
            return False

        partners = self._get_valid_carrier_partners()
        valid_accounts = partners.mapped("carrier_account_ids").filtered(
            lambda account: account.delivery_carrier_id == self.carrier_id
        )
        return bool(valid_accounts)

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
            partners = rec._get_valid_carrier_partners()
            if rec.carrier_id and partners:
                rec.valid_carrier_account_ids = partners.mapped(
                    "carrier_account_ids"
                ).filtered(
                    lambda account: account.delivery_carrier_id == rec.carrier_id
                )
            else:
                rec.valid_carrier_account_ids = partners.mapped("carrier_account_ids")

    @api.depends("delivery_billing_mode", "sender_id", "recipient_id")
    def _compute_valid_carrier_ids(self):
        """Compute all valid carriers for the current billing mode and partners."""
        for rec in self:
            partners = rec._get_valid_carrier_partners()
            rec.valid_carrier_ids = partners.mapped(
                "carrier_account_ids.delivery_carrier_id"
            )

    def _on_carrier_fields_changed(self):
        pass

    @api.constrains("delivery_billing_mode", "carrier_id", "carrier_account_id")
    def _check_carrier_account(self):
        for rec in self:
            if (
                rec.carrier_account_id
                and rec.delivery_billing_mode
                and rec.valid_carrier_account_ids  # Use the computed field directly
                and rec.carrier_account_id not in rec.valid_carrier_account_ids
            ):
                _logger.warning(
                    "Billing mode: %s, sender: %s (commercial: %s), recipient: %s (commercial: %s), account: %s, id: %s, valid: %s",
                    rec.delivery_billing_mode,
                    rec.sender_id.name,
                    rec.sender_id.commercial_partner_id.name,
                    rec.recipient_id.name,
                    rec.recipient_id.commercial_partner_id.name,
                    rec.carrier_account_id.partner_id.name,
                    rec.carrier_account_id.id,
                    rec.valid_carrier_account_ids.ids,
                )

                if rec.delivery_billing_mode == "collect":
                    raise UserError(
                        f"Carrier account is not associated with the recipient, but billing mode is collect. Current object: {rec}"
                    )
                elif rec.delivery_billing_mode in ["prepaid", "ppc", "no charge"]:
                    raise UserError(
                        f"Carrier account is not associated with the sender, but billing mode is prepaid, ppc or no charge. Current object: {rec}"
                    )
                elif rec.delivery_billing_mode == "third party":
                    raise UserError(
                        f"Third party carrier account cannot belong to sender or recipient. Current object: {rec}"
                    )
