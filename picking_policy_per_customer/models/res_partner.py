from odoo import fields, models


class ResPartner(models.Model):
    """
    Extends the partner model to add customer-specific picking policy preferences.
    
    This extension allows setting a default picking (shipping) policy at the customer level,
    which will be used as the default value when creating sales orders for this customer.
    """
    _inherit = 'res.partner'

    picking_policy = fields.Selection([
        ('direct', 'Deliver each product when available'),
        ('one', 'Deliver all products at once')],
        string='Shipping Policy',
        help='Select how to handle multi-product deliveries:\n'
             '- Deliver each product when available: products will be shipped as soon as they are available\n'
             '- Deliver all products at once: products will be shipped altogether when all of them are available')
