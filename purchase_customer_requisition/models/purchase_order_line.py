from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    requisition_id = fields.Many2one(
        comodel_name="purchase.requisition",
        string="Agreement",
        store=True,
        compute="_compute_requisition_id",
        inverse="_inverse_requisition_id",
    )

    requisition_line_id = fields.Many2one(
        comodel_name="purchase.requisition.line",
        string="Requisition Line",
        compute="_compute_requisition_line_id",
    )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for line in res.filtered("requisition_id"):
            line.price_unit = line.requisition_line_id.price_unit
        return res

    @api.depends("requisition_id")
    def _compute_requisition_line_id(self):
        for line in self:
            candidates = line.requisition_id.line_ids.filtered(
                lambda req_line: req_line.product_id == line.product_id
            )
            line.requisition_line_id = candidates[0] if candidates else False

    @api.depends("order_id.requisition_id", "product_id")
    def _compute_requisition_id(self):
        for line in self:
            customer = line.sale_order_id.partner_id or line.group_id.partner_id
            if not customer:
                sale_order = line.move_dest_ids.group_id.sale_id
                if len(sale_order) == 1:
                    customer = sale_order.partner_id
            domain = [
                "|",
                ("requisition_id.vendor_id", "=", line.order_id.partner_id.id),
                (
                    "requisition_id.vendor_id.commercial_partner_id",
                    "=",
                    line.order_id.partner_id.id,
                ),
                ("product_id", "=", line.product_id.id),
            ]
            requisition = self.order_id.requisition_id
            if customer:
                domain += [
                    "|",
                    ("requisition_id.customer_ids", "in", [customer.id]),
                    ("requisition_id.customer_ids", "=", False),
                ]
            else:
                domain += [
                    "|",
                    (
                        "requisition_id",
                        "=",
                        requisition.id,
                    ),
                    ("requisition_id.customer_ids", "=", False),
                ]
            requisition_lines = self.env["purchase.requisition.line"].search(domain)
            # If the current order's requisition_id is in the possible lines, use it
            req_id = False
            if line.order_id.requisition_id and requisition_lines:
                req_id = requisition_lines.filtered(
                    lambda req_line: req_line.requisition_id
                    == line.order_id.requisition_id
                ).requisition_id
            if not req_id and requisition_lines:
                req_id = requisition_lines[0].requisition_id
            line.requisition_id = req_id

    def _inverse_requisition_id(self):
        pass

    def _find_candidate(
        self,
        product_id,
        product_qty,
        product_uom,
        location_id,
        name,
        origin,
        company_id,
        values,
    ):
        return super(
            PurchaseOrderLine, self.filtered(lambda line: not line.requisition_id)
        )._find_candidate(
            product_id,
            product_qty,
            product_uom,
            location_id,
            name,
            origin,
            company_id,
            values,
        )
