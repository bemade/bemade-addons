from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Configuration fields
    use_current_user = fields.Boolean(
        string='Use Current User as Invoice User',
        config_parameter='current_user_as_invoice_user.use_current_user',
        default=True,
        help='If checked, the current user will be set as the invoice user. Otherwise, a specific user will be used.'
    )

    current_user_as_follower = fields.Boolean(
        string='Add Current User as Follower',
        config_parameter='current_user_as_invoice_user.current_user_as_follower',
        default=False,
        help='If checked, the current user will be added as a follower to the invoice when using current user as invoice user.'
    )

    specific_invoice_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Specific Invoice User',
        config_parameter='current_user_as_invoice_user.specific_user_id',
        help='User to be set as invoice user when not using current user',
        depends=['use_current_user']
    )
    
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        use_current_user = ICP.get_param('current_user_as_invoice_user.use_current_user', 'True')
        current_user_as_follower = ICP.get_param('current_user_as_invoice_user.current_user_as_follower', 'False')
        res.update({
            'use_current_user': use_current_user == 'True',
            'current_user_as_follower': current_user_as_follower == 'True',
        })
        if specific_user_id := ICP.get_param('current_user_as_invoice_user.specific_user_id'):
            res.update({
                'specific_invoice_user_id': int(specific_user_id),
            })
        return res
    
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('current_user_as_invoice_user.use_current_user', str(self.use_current_user))
        ICP.set_param('current_user_as_invoice_user.current_user_as_follower', str(self.current_user_as_follower))
        if self.specific_invoice_user_id:
            ICP.set_param('current_user_as_invoice_user.specific_user_id', str(self.specific_invoice_user_id.id))

