from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    requisition_id = fields.Many2one(
        comodel_name="purchase.requisition",
        string="Agreement",
        store=True,
        compute="_compute_requisition_id",
        inverse="_inverse_requisition_id",
    )

    requisition_name = fields.Char(
        related="requisition_id.name",
        string="Agreement",
    )

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    @api.depends("order_id.requisition_id", "product_id")
    def _compute_requisition_id(self):
        for line in self:
            customer = line.sale_order_id.partner_id or line.group_id.partner_id
            if not customer:
                sale_order = line.order_id._get_sale_orders()
                if len(sale_order) == 1:
                    customer = sale_order.partner_id
            domain = [
                "|",
                ("requisition_id.vendor_id", "=", line.order_id.partner_id.id),
                (
                    "requisition_id.vendor_id.child_ids.commercial_partner_id",
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
            if line.order_id.requisition_id and requisition_lines:
                line.requisition_id = requisition_lines.filtered(
                    lambda req_line: req_line.requisition_id
                    == line.order_id.requisition_id
                ).requisition_id
            if not line.requisition_id and requisition_lines:
                line.requisition_id = requisition_lines[0].requisition_id
            else:
                line.requisition_id = False

    def _inverse_requisition_id(self):
        pass

    @api.model
    def _prepare_purchase_order_line(
        self, product_id, product_qty, product_uom, company_id, supplier, po
    ):
        res = super()._prepare_purchase_order_line(
            product_id, product_qty, product_uom, company_id, supplier, po
        )
        # Si on a une réquisition, on ne veut pas regrouper les lignes
        if po.requisition_id:
            existing_line = po.order_line.filtered(
                lambda l: l.product_id == product_id
                and l.requisition_id == po.requisition_id
            )
            if existing_line:
                # Créer une nouvelle ligne au lieu de mettre à jour la quantité
                res["product_qty"] = product_qty
            else:
                res["product_qty"] = product_qty
        return res

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
