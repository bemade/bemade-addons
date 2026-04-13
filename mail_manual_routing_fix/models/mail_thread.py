# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, models
from odoo.tools.mail import plaintext2html


class MailThread(models.AbstractModel):
    """Fix HTML escaping and preserve threading headers in lost messages.
    
    The original mail_manual_routing module:
    1. Always escapes the body with escape(), breaking HTML emails
    2. Doesn't store In-Reply-To and References headers for later threading
    
    This override fixes both issues.
    """
    _inherit = 'mail.thread'

    @api.returns("mail.message", lambda value: value.id)
    def _create_lost_message(self, body="", body_is_html=False, **kwargs):
        """Override to fix HTML body handling and store threading headers.
        
        Changes from original:
        - If body_is_html is True, use Markup() to preserve HTML
        - If body_is_html is False, convert plain text to HTML with plaintext2html()
        - Store in_reply_to and references in dedicated fields for threading
        """
        # Fix HTML escaping
        if body:
            if body_is_html:
                # Body is already HTML - mark as safe to prevent escaping
                body = Markup(body)
            else:
                # Body is plain text - convert to HTML properly
                body = plaintext2html(body)
            body_is_html = True
        
        # Call parent to create the message
        message = super()._create_lost_message(body=body, body_is_html=body_is_html, **kwargs)
        
        # Store threading headers on the created message
        threading_vals = {}
        if kwargs.get('in_reply_to'):
            threading_vals['lost_in_reply_to'] = kwargs['in_reply_to']
        if kwargs.get('references'):
            threading_vals['lost_references'] = kwargs['references']
        
        if threading_vals:
            message.write(threading_vals)
        
        return message
