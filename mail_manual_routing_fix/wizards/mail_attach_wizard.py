# -*- coding: utf-8 -*-
import re

from odoo import fields, models


class MailMessageAttachWizard(models.TransientModel):
    """Extend attach wizard to preserve threading and track origin.
    
    The original wizard uses a raw SQL UPDATE that loses threading metadata.
    This override preserves parent_id, in_reply_to, and references fields,
    and marks messages as coming from lost messages.
    """
    _inherit = 'mail.message.attach.wizard'

    def action_attach_mail_message(self):
        """Override to preserve threading metadata and track origin."""
        self.ensure_one()
        
        message = self.env['mail.message'].browse(self.env.context.get('active_id'))
        if not message:
            return super().action_attach_mail_message()
        
        # Parse the reference to get model and res_id
        if not self.res_reference:
            return super().action_attach_mail_message()
        
        model, res_id = self._parse_reference(self.res_reference)
        if not model or not res_id:
            return super().action_attach_mail_message()
        
        # Find parent message for threading
        parent_id = self._find_parent_message(message, model, res_id)
        
        # Prepare values preserving threading
        values = {
            'model': model,
            'res_id': res_id,
            'is_unattached': False,
            'lost_origin': True,
        }
        
        if parent_id:
            values['parent_id'] = parent_id
        
        # Update message with ORM to trigger proper hooks
        message.write(values)
        
        # Post notification on target record
        record = self.env[model].browse(res_id)
        if hasattr(record, 'message_post'):
            record.message_post(
                body=f"Message attached from Lost Messages by {self.env.user.name}",
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        
        return {'type': 'ir.actions.act_window_close'}

    def _parse_reference(self, reference):
        """Parse a reference string like 'sale.order,123' into (model, res_id)."""
        if not reference:
            return None, None
        
        # Handle Reference field format
        if hasattr(reference, '_name'):
            return reference._name, reference.id
        
        # Handle string format "model,id"
        if isinstance(reference, str) and ',' in reference:
            parts = reference.split(',')
            if len(parts) == 2:
                try:
                    return parts[0], int(parts[1])
                except (ValueError, TypeError):
                    pass
        
        return None, None

    def _find_parent_message(self, message, model, res_id):
        """Find parent message based on stored In-Reply-To and References headers."""
        parent_id = None
        
        # Try to find parent via In-Reply-To header (stored in lost_in_reply_to)
        in_reply_to = message.lost_in_reply_to
        if in_reply_to:
            parent = self.env['mail.message'].search([
                ('message_id', '=', in_reply_to),
                ('model', '=', model),
                ('res_id', '=', res_id),
            ], limit=1)
            if parent:
                parent_id = parent.id
        
        # If no parent found, try References header (stored in lost_references)
        if not parent_id:
            references = message.lost_references
            if references:
                # References can contain multiple message IDs, try each
                ref_ids = self._extract_message_ids(references)
                for ref_id in reversed(ref_ids):  # Start from most recent
                    parent = self.env['mail.message'].search([
                        ('message_id', '=', ref_id),
                        ('model', '=', model),
                        ('res_id', '=', res_id),
                    ], limit=1)
                    if parent:
                        parent_id = parent.id
                        break
        
        return parent_id

    def _extract_message_ids(self, references):
        """Extract message IDs from References header string."""
        if not references:
            return []
        # Message IDs are enclosed in angle brackets - keep the brackets
        # as Odoo stores message_id with brackets
        return re.findall(r'<[^>]+>', references)
