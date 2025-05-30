# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.tools import email_normalize


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        """Override _notify_thread to disable notifications for MSG file imports.
        
        When processing a message that comes from an MSG file import, we want to
        disable all notifications to avoid sending automatic responses.
        
        Returns:
            list: Empty list of recipients when is_msg_import is True, otherwise normal recipients data
        """
        # Check if this is called from MSG processing
        if self.env.context.get('is_msg_import', False):
            # Return empty recipients list for MSG imports
            return []
        
        return super()._notify_thread(message, msg_vals=msg_vals, **kwargs)
