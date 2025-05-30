from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    msg_max_file_size = fields.Integer(
        string='Maximum MSG File Size (MB)',
        config_parameter='msg_attachments.max_file_size',
        default=25
    )

    msg_format_metadata = fields.Boolean(
        string='Show Email Metadata in Message',
        config_parameter='msg_attachments.format_metadata',
        default=True
    )

    msg_attachment_mode = fields.Selection([
        ('all', 'Process All Attachments'),
        ('skip_empty', 'Skip Empty Attachments'),
        ('selective', 'Process Selected Types Only')
    ], string='Attachment Processing Mode',
        config_parameter='msg_attachments.attachment_mode',
        default='all'
    )

    msg_allowed_extensions = fields.Char(
        string='Allowed Attachment Extensions',
        config_parameter='msg_attachments.allowed_extensions',
        default='.pdf,.doc,.docx,.xls,.xlsx,.jpg,.png',
        help='Comma-separated list of allowed file extensions'
    )

    log_msg_error = fields.Boolean(
        string='Log MSG Import Errors',
        config_parameter='msg_attachments.log_msg_error',
        default=False
    )

