# -*- coding: utf-8 -*-
from odoo import fields, models


class MailMessage(models.Model):
    """Add lost message tracking fields.
    
    - Threading headers: in_reply_to and references are stored to enable proper
      thread reconstruction when routing lost messages.
    - Origin tracking: lost_origin flag to identify routed messages.
      Note: write_date and write_uid provide routed date/user info.
    """
    _inherit = 'mail.message'

    # Threading headers (stored during lost message creation)
    lost_in_reply_to = fields.Char(
        string="In-Reply-To",
        help="Original In-Reply-To header from the email, used for threading.",
    )
    lost_references = fields.Text(
        string="Email References",
        help="Original References header from the email, used for threading.",
    )

    # Origin tracking (set when message is routed)
    # Note: write_date and write_uid provide when/who routed the message
    lost_origin = fields.Boolean(
        string="From Lost Messages",
        default=False,
        help="Indicates this message was originally a lost message that was manually routed.",
    )
