from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enforce_customer_reference = fields.Boolean(
        string="Require Customer Reference on Sales Orders",
        config_parameter='sale_mandatory_customer_reference.enforce_customer_reference',
        help="When enabled, sales orders cannot be confirmed without a customer reference "
             "(except for online payments where it will be set to 'Credit Card')."
    )
