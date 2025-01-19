from odoo import models, fields, api
from odoo.addons.purchase.models.purchase_order_line import PurchaseOrderLine as BasePOL


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

    def _compute_price_unit_and_date_planned_and_name(self):
        super()._compute_price_unit_and_date_planned_and_name()
        po_lines_with_requisition = self.filtered("requisition_id")
        for line in po_lines_with_requisition:
            line.price_unit = line.requisition_line_id.price_unit
        po_lines_without_requisition = self - po_lines_with_requisition
        to_compute_basic = self.env["purchase.order.line"]
        for line in po_lines_without_requisition:
            po_agreement_customers = line.order_id.requisition_id.customer_ids
            customer = line._get_customer()
            if po_agreement_customers and customer not in po_agreement_customers:
                to_compute_basic |= line
        func = BasePOL._compute_price_unit_and_date_planned_and_name
        func(to_compute_basic)

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
            customer = line._get_customer()
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

    def _get_customer(self):
        self.ensure_one()
        customer = self.sale_order_id.partner_id or self.group_id.partner_id
        if not customer:
            sale_order = self.move_dest_ids.group_id.sale_id
            if len(sale_order) == 1:
                customer = sale_order.partner_id
        return customer

    def _inverse_requisition_id(self):
        self._compute_price_unit_and_date_planned_and_name()

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
