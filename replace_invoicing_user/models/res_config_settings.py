from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Configuration fields
    use_current_user = fields.Boolean(
        string='Use Current User as Invoice User',
        config_parameter='current_user_as_invoice_user.use_current_user',
        default=True,
        help='If checked, the current user will be set as the invoice user. Otherwise, a specific user will be used.'
    )
    specific_invoice_user_id = fields.Many2one(
        'res.users',
        string='Specific Invoice User',
        config_parameter='current_user_as_invoice_user.specific_user_id',
        help='User to be set as invoice user when not using current user'
    )
