from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = ["purchase.order", "carrier.account.mixin"]
    _name = "purchase.order"

    recipient_id = fields.Many2one(
        comodel_name="res.partner",
        string="Recipient",
        related="picking_type_id.warehouse_id.partner_id",
    )

    sender_id = fields.Many2one(
        comodel_name="res.partner",
        string="Sender",
        related="partner_id",
    )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            carrier_id = rec.carrier_id
            account_id = rec.carrier_account_id
            billing_mode = rec.delivery_billing_mode

            if not carrier_id and rec.sender_id.purchase_delivery_carrier_id:
                carrier_id = rec.sender_id.purchase_delivery_carrier_id

            if carrier_id:

                def _predicate(account):
                    return account.delivery_carrier_id == carrier_id

                sender_accounts = (
                    rec.sender_id.commercial_partner_id.carrier_account_ids.filtered(
                        _predicate
                    )
                )
                recipient_accounts = (
                    rec.recipient_id.commercial_partner_id.carrier_account_ids.filtered(
                        _predicate
                    )
                )
                if not account_id:
                    if (
                        rec.partner_id.purchase_delivery_carrier_account_id
                        and rec.partner_id.purchase_delivery_carrier_account_id.delivery_carrier_id
                        == carrier_id
                    ):
                        account_id = rec.partner_id.purchase_delivery_carrier_account_id
                    else:
                        # Search for an account matching the carrier on the recipient
                        if recipient_accounts:
                            account_id = recipient_accounts[0]
                            continue
                        else:
                            if sender_accounts:
                                account_id = sender_accounts[0]
                if account_id and not billing_mode:
                    if account_id in sender_accounts:
                        billing_mode = "ppc"
                    elif account_id in recipient_accounts:
                        billing_mode = "collect"
                    else:
                        billing_mode = "third party"
                if any(
                    [
                        account_id != rec.carrier_account_id,
                        billing_mode != rec.delivery_billing_mode,
                        carrier_id != rec.carrier_id,
                    ]
                ):
                    rec.write(
                        {
                            "carrier_id": carrier_id.id,
                            "carrier_account_id": account_id.id,
                            "delivery_billing_mode": billing_mode,
                        }
                    )

        # Based on who owns the carrier account, set the delivery billing mode if it is
        # not already set
        for rec in res.filtered(
            lambda order: order.carrier_id
            and order.carrier_account_id
            and not order.delivery_billing_mode
        ):
            if rec.carrier_account_id in (
                self.sender_id.carrier_account_ids
                | self.sender_id.commercial_partner_id.carrier_account_ids
            ):
                rec.delivery_billing_mode = "prepaid"
            elif rec.carrier_account_id in (
                self.recipient_id.carrier_account_ids
                | self.recipient_id.commercial_partner_id.carrier_account_ids
            ):
                rec.delivery_billing_mode = "collect"
            else:
                rec.delivery_billing_mode = "third party"
        return res

    def write(self, vals):
        res = super().write(vals)
        if (
            "carrier_account_id" in vals
            or "carrier_id" in vals
            or "delivery_billing_mode" in vals
        ):
            for rec in self.filtered(
                lambda order: order.state not in ["draft", "sent"]
            ):
                for picking in rec.picking_ids.filtered(
                    lambda pick: pick.state not in ["done", "cancel"]
                ):
                    picking.carrier_id = rec.carrier_id
                    picking.delivery_billing_mode = rec.delivery_billing_mode
                    picking.carrier_account_id = rec.carrier_account_id
        return res

    def _prepare_picking(self):
        res = super()._prepare_picking()
        res.update(
            carrier_id=self.carrier_id.id,
            delivery_billing_mode=self.delivery_billing_mode,
            carrier_account_id=self.carrier_account_id.id,
        )
        return res
