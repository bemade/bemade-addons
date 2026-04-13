# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models


class MailInvalidAddressWizard(models.TransientModel):
    """Wizard to notify sender that they contacted an invalid address."""
    _name = 'mail.invalid.address.wizard'
    _description = 'Notify Invalid Address'

    message_id = fields.Many2one('mail.message', string="Original Message", required=True)
    sender_email = fields.Char(string="Sender Email", compute='_compute_sender_info', store=True)
    sender_name = fields.Char(string="Sender Name", compute='_compute_sender_info', store=True)
    original_subject = fields.Char(string="Original Subject", compute='_compute_sender_info', store=True)
    is_noreply = fields.Boolean(string="Is No-Reply", compute='_compute_is_noreply')
    reply_subject = fields.Char(string="Subject", default="Re: Invalid email address")
    reply_body = fields.Html(string="Body", default=lambda self: self._default_body())

    def _default_body(self):
        return """<p>Hello,</p>
<p>The email address you contacted is not monitored or does not accept incoming messages.</p>
<p>Please contact us through the appropriate channel.</p>
<p>Best regards</p>"""

    @api.depends('message_id')
    def _compute_sender_info(self):
        for wizard in self:
            if wizard.message_id:
                wizard.sender_email = wizard.message_id.email_from
                wizard.sender_name = wizard._extract_name(wizard.message_id.email_from)
                wizard.original_subject = wizard.message_id.subject
            else:
                wizard.sender_email = False
                wizard.sender_name = False
                wizard.original_subject = False

    @api.depends('sender_email')
    def _compute_is_noreply(self):
        noreply_patterns = ['noreply', 'no-reply', 'donotreply', 'do-not-reply', 'mailer-daemon']
        for wizard in self:
            email = (wizard.sender_email or '').lower()
            wizard.is_noreply = any(p in email for p in noreply_patterns)

    def _extract_name(self, email_from):
        """Extract name from email format 'Name <email@domain.com>'."""
        if not email_from:
            return ''
        match = re.match(r'^"?([^"<]+)"?\s*<', email_from)
        if match:
            return match.group(1).strip()
        return email_from.split('@')[0] if '@' in email_from else email_from

    def action_send_notification(self):
        """Send notification email to the sender."""
        self.ensure_one()
        
        # Create and send mail
        mail_values = {
            'subject': self.reply_subject,
            'body_html': self.reply_body,
            'email_to': self.sender_email,
            'auto_delete': True,
        }
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
        
        # Mark original message with subcategory if exists
        subcategory = self.env.ref('mail_manual_routing_ux.subcategory_new_inquiry', raise_if_not_found=False)
        if subcategory:
            self.message_id.write({'lost_subcategory_id': subcategory.id})
        
        return {'type': 'ir.actions.act_window_close'}

    def action_skip(self):
        """Skip notification and mark as auto-reply."""
        self.ensure_one()
        subcategory = self.env.ref('mail_manual_routing_ux.subcategory_auto_reply', raise_if_not_found=False)
        if subcategory:
            self.message_id.write({'lost_subcategory_id': subcategory.id})
        return {'type': 'ir.actions.act_window_close'}
