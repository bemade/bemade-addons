from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    customer_requisition_ref = fields.Char(
        string='Customer Requisition Ref',
        compute='_compute_customer_requisition_ref',
        store=True,
        help='Customer requisition reference for this supplier'
    )

    @api.depends('sale_line_id.order_id.partner_id', 'order_id.partner_id')
    def _compute_customer_requisition_ref(self):
        for line in self:
            if line.sale_line_id and line.sale_line_id.order_id.partner_id and line.order_id.partner_id:
                requisition = self.env['customer.supplier.requisition'].search([
                    ('customer_id', '=', line.sale_line_id.order_id.partner_id.id),
                    ('supplier_id', '=', line.order_id.partner_id.id)
                ], limit=1)
                line.customer_requisition_ref = requisition.requisition_ref if requisition else False
            else:
                line.customer_requisition_ref = False

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.customer_requisition_ref:
                if line.name:
                    line.name = f"[{line.customer_requisition_ref}] {line.name}"
        return lines
