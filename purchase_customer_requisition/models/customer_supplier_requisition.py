from odoo import models, fields, api

class CustomerSupplierRequisition(models.Model):
    _name = 'customer.supplier.requisition'
    _description = 'Customer Supplier Requisition Reference'

    customer_id = fields.Many2one(
        comodel_name='res.partner', 
        string='Customer', 
        required=True,
        domain=[
            ('customer_rank', '>', 0)
            ]
        )

    supplier_id = fields.Many2one(
        comodel_name='res.partner', 
        string='Supplier', 
        required=True,
        domain=[
            ('supplier_rank', '>', 0)]
            )

    requisition_ref = fields.Char(
        string='Requisition Reference', 
        required=True,
        help='Reference number used by the supplier for this customer'
        )

    active = fields.Boolean(
        default=True
        )

    _sql_constraints = [
        ('unique_customer_supplier', 'unique(customer_id, supplier_id)',
         'A requisition reference already exists for this customer-supplier pair!')
    ]
