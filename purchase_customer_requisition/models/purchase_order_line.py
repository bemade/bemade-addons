from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    customer_ids = fields.Many2many(
        # related='order_id.requisition_id.customer_ids',
        string="Customers",
        store=True,
        help="Customers associated with this purchase order line",
    )

    requisition_id = fields.Many2one(
        related="order_id.requisition_id", string="Purchase Requisition", store=True
    )

    requisition_name = fields.Char(
        related="requisition_id.name",
        string="Agreement",
    )

    def _get_product_purchase_description(self, product_lang):
        name = super()._get_product_purchase_description(product_lang)
        if self.requisition_id:
            name = f"[REQ/{self.requisition_id.name}] {name}"
        if self.customer_ids:
            name = f"[{', '.join(self.customer_ids.mapped('name'))}] {name}"
        return name

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

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.name:
                name = line.name
                if line.requisition_id:
                    name = f"[REQ/{line.requisition_id.name}] {name}"
                if line.customer_ids:
                    name = f"[{', '.join(line.customer_ids.mapped('name'))}] {name}"
                line.name = name
        return lines

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
