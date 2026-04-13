# -*- coding: utf-8 -*-
from odoo import fields, models


class MailMessageCategorizeWizard(models.TransientModel):
    """Wizard to categorize multiple messages at once."""
    _name = 'mail.message.categorize.wizard'
    _description = 'Categorize Lost Messages'

    message_ids = fields.Many2many('mail.message', string="Messages")
    subcategory_id = fields.Many2one(
        'lost.message.subcategory',
        string="Subcategory",
        required=True,
    )

    def action_categorize(self):
        """Apply subcategory to all selected messages."""
        self.message_ids.write({'lost_subcategory_id': self.subcategory_id.id})
        return {'type': 'ir.actions.act_window_close'}


class MailMessageDeleteWizard(models.TransientModel):
    """Wizard to confirm batch deletion of messages."""
    _name = 'mail.message.delete.wizard'
    _description = 'Delete Lost Messages'

    message_ids = fields.Many2many('mail.message', string="Messages")
    message_count = fields.Integer(
        string="Message Count",
        compute='_compute_message_count',
    )

    def _compute_message_count(self):
        for wizard in self:
            wizard.message_count = len(wizard.message_ids)

    def action_delete(self):
        """Delete all selected messages."""
        self.message_ids.unlink()
        return {'type': 'ir.actions.act_window_close'}
