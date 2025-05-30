from odoo import models, fields, api

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    is_msg_file = fields.Boolean(
        string='Is MSG File',
        compute='_compute_is_msg_file',
        store=True,
        help='Technical field to identify MSG files'
    )

    @api.depends('mimetype', 'name')
    def _compute_is_msg_file(self):
        for attachment in self:
            attachment.is_msg_file = (
                attachment.mimetype == 'application/vnd.ms-outlook' or
                (attachment.name and attachment.name.lower().endswith('.msg'))
            )

    def _get_mimetype(self):
        """Override to add MSG file mimetype detection."""
        mimetype = super()._get_mimetype()
        if not mimetype and self.name and self.name.lower().endswith('.msg'):
            return 'application/vnd.ms-outlook'
        return mimetype
