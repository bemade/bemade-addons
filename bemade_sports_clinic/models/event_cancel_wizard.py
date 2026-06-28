from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SportsEventCancelWizard(models.TransientModel):
    _name = 'sports.event.cancel.wizard'
    _description = 'Sports Event Cancel Wizard'

    event_id = fields.Many2one('sports.event', string='Event', required=True, readonly=True)
    reason = fields.Text(string='Reason', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and 'event_id' in fields_list:
            res['event_id'] = active_id
        return res

    def action_confirm_cancel(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_("Please provide a cancellation reason."))

        event = self.event_id
        if not event or not event.exists():
            raise UserError(_("Event not found."))

        if event.state in ('cancelled', 'invoiced'):
            raise UserError(_("This event cannot be cancelled."))

        reason = self.reason.strip()
        # cancel_reason flows into sports.event.write where the centralised
        # assigned-staff cancellation notice is fired.
        event.with_context(cancel_reason=reason).write({'state': 'cancelled'})
        try:
            event.message_post(body=_('Event cancelled. Reason: %s') % (reason,))
        except Exception:
            pass

        return {'type': 'ir.actions.act_window_close'}
