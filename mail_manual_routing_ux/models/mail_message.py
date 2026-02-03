# -*- coding: utf-8 -*-
from odoo import fields, models


class MailMessage(models.Model):
    """Extend mail.message with subcategory and batch actions."""
    _inherit = 'mail.message'

    lost_subcategory_id = fields.Many2one(
        'lost.message.subcategory',
        string="Subcategory",
        help="Classification of this lost message.",
    )

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
