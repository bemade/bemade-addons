# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MailFinanceTriageWizard(models.TransientModel):
    """Extend finance triage wizard with helpdesk integration."""
    _inherit = 'mail.finance.triage.wizard'

    helpdesk_team_id = fields.Many2one('helpdesk.team', string="Helpdesk Team")

    @api.depends_context('uid')
    def _compute_has_helpdesk(self):
        """Override to return True since helpdesk is installed."""
        for wizard in self:
            wizard.has_helpdesk = True

    def _create_helpdesk_tickets(self):
        """Create helpdesk tickets for each message."""
        if not self.helpdesk_team_id:
            return {'type': 'ir.actions.act_window_close'}

        HelpdeskTicket = self.env['helpdesk.ticket']
        tickets = self.env['helpdesk.ticket']

        for message in self.message_ids:
            ticket = HelpdeskTicket.create({
                'name': message.subject or 'Finance inquiry',
                'team_id': self.helpdesk_team_id.id,
                'description': message.body,
                'partner_email': message.email_from,
            })
            tickets |= ticket

            # Mark message as processed
            subcategory = self.env.ref(
                'mail_manual_routing_ux.subcategory_finance',
                raise_if_not_found=False
            )
            if subcategory:
                message.write({'lost_subcategory_id': subcategory.id})

        # Return action to view created tickets
        if len(tickets) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'helpdesk.ticket',
                'res_id': tickets.id,
                'view_mode': 'form',
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'domain': [('id', 'in', tickets.ids)],
            'view_mode': 'list,form',
        }
