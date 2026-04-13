# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import fields, models


class MailMessage(models.Model):
    """Extend mail.message with subcategory and batch actions."""
    _inherit = 'mail.message'

    lost_subcategory_id = fields.Many2one(
        'lost.message.subcategory',
        string="Subcategory",
        help="Classification of this lost message.",
    )

    def write(self, vals):
        """Log subcategory changes into lost_comments as a simple audit trail."""
        if 'lost_subcategory_id' not in vals:
            return super().write(vals)

        # Capture old subcategory names before writing
        old_subcats = {
            rec.id: rec.lost_subcategory_id.name or 'None'
            for rec in self
        }

        result = super().write(vals)

        # Build log entry for each record that changed
        user_name = self.env.user.name
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        for rec in self:
            new_name = rec.lost_subcategory_id.name or 'None'
            old_name = old_subcats[rec.id]
            if old_name != new_name:
                entry = f"[{timestamp}] {user_name}: Subcategory: {old_name} → {new_name}"
                existing = rec.lost_comments or ''
                # Use super().write() to avoid recursion
                super(MailMessage, rec).write({
                    'lost_comments': (existing + '\n' + entry).strip()
                })
        return result

    def action_categorize(self):
        """Open wizard to categorize selected messages."""
        return {
            'name': 'Categorize Messages',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.message.categorize.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_message_ids': [(6, 0, self.ids)]},
        }

    def action_batch_delete(self):
        """Open wizard to confirm batch deletion."""
        return {
            'name': 'Delete Messages',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.message.delete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_message_ids': [(6, 0, self.ids)]},
        }

    def action_notify_invalid_address(self):
        """Open wizard to notify sender of invalid address."""
        self.ensure_one()
        return {
            'name': 'Notify Invalid Address',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.invalid.address.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_message_id': self.id},
        }

    def action_finance_triage(self):
        """Open wizard for finance message triage."""
        return {
            'name': 'Finance Triage',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.finance.triage.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_message_ids': [(6, 0, self.ids)]},
        }
