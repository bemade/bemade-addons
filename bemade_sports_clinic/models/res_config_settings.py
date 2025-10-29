from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Vendor-side (therapist purchase) products
    product_event_coverage_vendor_id = fields.Many2one(
        'product.product', string='Therapist Coverage Product (Vendor PO)',
        config_parameter='bemade_sports_clinic.product_event_coverage_vendor_id')
    product_event_travel_vendor_id = fields.Many2one(
        'product.product', string='Therapist Travel Product (Vendor PO)',
        config_parameter='bemade_sports_clinic.product_event_travel_vendor_id')
    product_event_clinic_vendor_id = fields.Many2one(
        'product.product', string='Clinic Product (Vendor PO)',
        config_parameter='bemade_sports_clinic.product_event_clinic_vendor_id')

    # Customer-side (organization invoice) products
    product_event_coverage_customer_id = fields.Many2one(
        'product.product', string='Coverage Product (Customer Invoice)',
        config_parameter='bemade_sports_clinic.product_event_coverage_customer_id')
    product_event_travel_customer_id = fields.Many2one(
        'product.product', string='Travel Product (Customer Invoice)',
        config_parameter='bemade_sports_clinic.product_event_travel_customer_id')
    product_event_clinic_customer_id = fields.Many2one(
        'product.product', string='Clinic Product (Customer Invoice)',
        config_parameter='bemade_sports_clinic.product_event_clinic_customer_id')
