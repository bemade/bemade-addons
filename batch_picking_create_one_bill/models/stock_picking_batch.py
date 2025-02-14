# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

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
        store=True,
    )
    invoice_count = fields.Integer(
        string="Nombre de factures",
        compute="_compute_invoice_count",
        store=True,
        compute_sudo=True,
    )

    def _prepare_move_line_vals(self, **kwargs):
        vals = super()._prepare_move_line_vals(**kwargs)
        if self.zero_quantity_default:
            vals["quantity"] = 0.0
        return vals

    @api.depends("picking_ids.move_ids.purchase_line_id.order_id.invoice_ids")
    def _compute_invoice_ids(self):
        for batch in self:
            purchase_orders = batch.picking_ids.move_ids.purchase_line_id.order_id
            batch.invoice_ids = purchase_orders.invoice_ids

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for batch in self:
            batch.invoice_count = len(batch.invoice_ids)

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

    @api.constrains("picking_ids")
    def _check_purchase_orders(self):
        for batch in self:
            partners = batch.picking_ids.purchase_id.partner_id
            if len(partners) > 1:
                raise ValidationError(
                    "Tous les bons de commande du batch doivent provenir du même fournisseur."
                )

    def action_confirm(self):
        """Override to set zero quantity on move lines at confirmation of the batch"""
        res = super().action_confirm()
        self.filtered("zero_quantity_default").move_line_ids.write({"quantity": 0})
        return res
