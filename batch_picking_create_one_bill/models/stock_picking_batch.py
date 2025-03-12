# -*- coding: utf-8 -*-
from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    purchase_order_ids = fields.Many2many(
        "purchase.order",
        string="Bons de commande",
        compute="_compute_purchase_orders",
        compute_sudo=True,
    )

    partner_ids = fields.Many2many(
        "res.partner",
        string="Fournisseur",
        compute="_compute_partner",
        compute_sudo=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Handle zero_quantity_default from context if not explicitly set in vals
        for vals in vals_list:
            if (
                "zero_quantity_default" not in vals
                and self.env.context.get("default_zero_quantity_default") is not None
            ):
                vals["zero_quantity_default"] = self.env.context.get(
                    "default_zero_quantity_default"
                )
        return super().create(vals_list)

    zero_quantity_default = fields.Boolean(
        string="Quantités à zéro par défaut",
        default=True,
        help="Initialiser les quantités à zéro lors de la création du batch",
    )
    invoice_ids = fields.Many2many(
        "account.move",
        string="Factures associées",
        compute="_compute_invoice_ids",
        compute_sudo=True,
    )
    invoice_count = fields.Integer(
        string="Nombre de factures",
        compute="_compute_invoice_count",
        compute_sudo=True,
    )

    # Field computation methods

    @api.depends("picking_ids.move_ids.purchase_line_id.order_id")
    def _compute_purchase_orders(self):
        for batch in self:
            batch.purchase_order_ids = (
                batch.picking_ids.move_ids.purchase_line_id.order_id
            )

    @api.depends("purchase_order_ids")
    def _compute_partner(self):
        for wizard in self:
            wizard.partner_ids = wizard.purchase_order_ids.mapped("partner_id")

    def _prepare_move_line_vals(self, **kwargs):
        vals = super()._prepare_move_line_vals(**kwargs)
        if self.zero_quantity_default:
            vals["quantity"] = 0.0
        return vals

    @api.depends("move_line_ids.move_id.purchase_line_id.order_id.invoice_ids")
    def _compute_invoice_ids(self):
        for batch in self:
            batch.invoice_ids = (
                batch.move_line_ids.move_id.purchase_line_id.invoice_lines.move_id
            )

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for batch in self:
            batch.invoice_count = len(batch.invoice_ids)

    # Actions

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "account.action_move_in_invoice_type"
        )
        if self.invoice_count == 1:
            action["views"] = [(False, "form")]
            action["res_id"] = self.invoice_ids.id
        else:
            action["domain"] = [("id", "in", self.invoice_ids.ids)]
        return action

    def action_confirm(self):
        """Override to set zero quantity on move lines at confirmation of the batch"""
        res = super().action_confirm()
        self.filtered("zero_quantity_default").move_line_ids.write({"quantity": 0})
        return res

    def action_create_bill(self):
        self.ensure_one()
        if not self.purchase_order_ids:
            raise ValidationError(_("No purchase orders found in this batch."))

        if len(self.partner_ids) > 1:
            raise ValidationError(_("The batch must have only one supplier."))

        bill = self.env["account.move"].create(self._get_bill_values())
        return self._get_view_bill_action(bill)

    # Helpers

    def _get_view_bill_action(self, bill):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "account.action_move_in_invoice_type"
        )
        action["views"] = [(False, "form")]
        action["res_id"] = bill.id
        return action

    def _get_currency_id(self):
        currency_id = self.purchase_order_ids.mapped("currency_id")
        if len(currency_id) > 1:
            raise UserError(_("The selected receipts do not have the same currency."))
        return currency_id.id

    def _get_bill_values(self):
        """Build a dictionary of the values for the vendor bill to create."""

        company_id = self.company_id.id
        partner_id = self.partner_ids.id
        invoice_date = self.scheduled_date
        invoice_origin = ", ".join(self.purchase_order_ids.mapped("name"))
        move_line_ids = self._get_line_values()
        currency_id = self._get_currency_id()
        return {
            "company_id": company_id,
            "partner_id": partner_id,
            "move_type": "in_invoice",
            "invoice_date": invoice_date,
            "invoice_origin": invoice_origin,
            "currency_id": currency_id,
            "line_ids": move_line_ids,
        }

    def _get_line_values(self):
        """For each of the stock.move.line in the batch, build a dictionary of values for the invoice line to match."""
        line_vals = []
        for move_line in self.move_line_ids:
            purchase_line_id = move_line.move_id.purchase_line_id
            line_vals.append(
                Command.create(
                    {
                        "product_id": move_line.product_id.id,
                        "quantity": move_line.quantity,
                        "price_unit": purchase_line_id.price_unit,
                        "discount": purchase_line_id.discount,
                        "purchase_line_id": purchase_line_id.id,
                    }
                )
            )
        return line_vals
