"""Assigned staff are alerted when an event they're on is cancelled or deleted.

Acceptance criteria:
- Cancelling an event (statusbar ``action_cancel``, the cancel wizard, or the
  portal controller — all funnel through ``write({'state': 'cancelled'})``)
  notifies every assigned staff member (an in-app message that lists each
  assignee partner as a recipient, delivered by email/inbox per their pref).
- Deleting an event notifies the assigned staff captured before deletion.
- A single cancel produces exactly one cancellation notice (no duplicate from
  ``write`` + ``action_cancel`` both firing).
- Re-cancelling an already-cancelled event does not re-notify.
- The cancellation reason (wizard/portal) is carried into the notice.
- An event with no assigned staff cancels/deletes without error.
"""

from datetime import datetime

from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestEventCancelNotifications(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({
            'name': 'Notif Org', 'is_company': True,
        })
        cls.team = cls.env['sports.team'].create({
            'name': 'Notif Team', 'parent_id': cls.org.id,
        })
        internal = cls.env.ref('base.group_user').id
        tp = cls.env.ref(
            'bemade_sports_clinic.group_sports_clinic_treatment_professional'
        ).id
        cls.staff1 = cls.env['res.users'].create({
            'name': 'Staff One', 'login': 'notif.staff1@example.com',
            'email': 'notif.staff1@example.com',
            'group_ids': [(6, 0, [internal, tp])],
        })
        cls.staff2 = cls.env['res.users'].create({
            'name': 'Staff Two', 'login': 'notif.staff2@example.com',
            'email': 'notif.staff2@example.com',
            'group_ids': [(6, 0, [internal, tp])],
        })
        cls.staff_partners = cls.staff1.partner_id | cls.staff2.partner_id

    def _make_event(self, with_staff=True, **vals):
        staff = [self.staff1.id, self.staff2.id] if with_staff else []
        return self.env['sports.event'].create({
            'name': vals.pop('name', 'Notif Event'),
            'team_ids': [Command.set([self.team.id])],
            'assigned_staff_ids': [Command.set(staff)],
            'date_start': datetime(2026, 3, 5, 10, 0),
            'date_end': datetime(2026, 3, 5, 12, 0),
            'state': 'confirmed',
            **vals,
        })

    def _cancel_notices(self, event):
        """Messages on the event that notify at least one assigned staff.

        The notice is sent via message_notify (user_notification type), which
        the message_ids one2many deliberately filters out — search
        mail.message directly."""
        messages = self.env['mail.message'].search([
            ('model', '=', 'sports.event'),
            ('res_id', '=', event.id),
        ])
        return messages.filtered(
            lambda m: self.staff_partners & m.notified_partner_ids
        )

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_action_cancel_notifies_each_assigned_staff(self):
        event = self._make_event()
        event.action_cancel()
        self.assertEqual(event.state, 'cancelled')
        notices = self._cancel_notices(event)
        # Exactly one cancellation notice (no duplicate from write + action_cancel).
        self.assertEqual(
            len(notices), 1,
            "exactly one cancellation notice should reach assigned staff",
        )
        notified = notices.notified_partner_ids
        self.assertIn(self.staff1.partner_id, notified)
        self.assertIn(self.staff2.partner_id, notified)

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_cancel_wizard_notifies_with_reason(self):
        event = self._make_event()
        wizard = self.env['sports.event.cancel.wizard'].create({
            'event_id': event.id, 'reason': 'Field flooded',
        })
        wizard.action_confirm_cancel()
        self.assertEqual(event.state, 'cancelled')
        notices = self._cancel_notices(event)
        self.assertTrue(notices, "wizard cancel should notify assigned staff")
        self.assertIn(self.staff1.partner_id, notices.notified_partner_ids)
        self.assertIn(self.staff2.partner_id, notices.notified_partner_ids)
        self.assertTrue(
            any('Field flooded' in (m.body or '') for m in notices),
            "the cancellation reason should appear in the staff notice",
        )

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_write_cancel_carries_reason_via_context(self):
        # Mirrors what the portal controller does: write with cancel_reason ctx.
        event = self._make_event()
        event.with_context(cancel_reason='Coach unavailable').write(
            {'state': 'cancelled'}
        )
        notices = self._cancel_notices(event)
        self.assertTrue(notices)
        self.assertTrue(
            any('Coach unavailable' in (m.body or '') for m in notices),
        )

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_recancel_does_not_renotify(self):
        event = self._make_event()
        event.action_cancel()
        first = self._cancel_notices(event)
        self.assertEqual(len(first), 1)
        # Writing state='cancelled' again must not produce a new notice.
        event.write({'state': 'cancelled'})
        self.assertEqual(
            len(self._cancel_notices(event)), 1,
            "re-cancelling an already-cancelled event must not re-notify",
        )

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_unlink_notifies_captured_staff(self):
        event = self._make_event(name='Doomed Event')
        pre = self.env['mail.message'].search([
            ('notified_partner_ids', 'in', self.staff_partners.ids),
        ])
        event.unlink()
        new = self.env['mail.message'].search([
            ('notified_partner_ids', 'in', self.staff_partners.ids),
            ('id', 'not in', pre.ids),
        ])
        self.assertTrue(new, "deleting an event should notify assigned staff")
        notified = new.notified_partner_ids
        self.assertIn(self.staff1.partner_id, notified)
        self.assertIn(self.staff2.partner_id, notified)
        self.assertTrue(
            any('Doomed Event' in (m.body or '') or 'Doomed Event' in (m.subject or '')
                for m in new),
            "the deletion notice should identify the event",
        )

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_portal_user_cancel_notifies_without_acl_error(self):
        # A portal therapist cancelling their own event (the controller path:
        # write with portal_cancel_event + cancel_reason) must reach the
        # assigned-staff notice without tripping res.users ACLs.
        portal = self.env.ref('base.group_portal').id
        tp = self.env.ref(
            'bemade_sports_clinic.group_portal_treatment_professional'
        ).id
        portal_tp = self.env['res.users'].with_context(
            no_reset_password=True
        ).create({
            'name': 'Portal TP', 'login': 'notif.portaltp@example.com',
            'email': 'notif.portaltp@example.com',
            'group_ids': [(6, 0, [portal, tp])],
        })
        self.env['sports.team.staff'].create({
            'team_id': self.team.id,
            'partner_id': portal_tp.partner_id.id,
            'role': 'therapist',
        })
        event = self._make_event()
        event.assigned_staff_ids = [Command.link(portal_tp.id)]
        event.with_user(portal_tp).with_context(
            portal_cancel_event=True, cancel_reason='Portal cancel',
        ).write({'state': 'cancelled'})
        self.assertEqual(event.state, 'cancelled')
        notices = self._cancel_notices(event)
        self.assertTrue(notices, "portal cancel should notify assigned staff")
        # EVERY assignee is notified, including the canceller: without
        # mail_notify_author the author is silently dropped, so a sole-assignee
        # portal TP cancelling their own event would notify nobody
        # (dev-review 2026-07-04).
        notified = notices.notified_partner_ids
        self.assertIn(self.staff1.partner_id, notified)
        self.assertIn(self.staff2.partner_id, notified)
        self.assertIn(portal_tp.partner_id, notified)

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_sole_assignee_canceller_still_notified(self):
        """Statusbar-style cancel (bare state write) by a user who is the only
        assignee must still produce a notification — the author-suppression
        regression found in dev-review 2026-07-04."""
        event = self._make_event(with_staff=False, name='Solo Cancel Event')
        event.assigned_staff_ids = [Command.link(self.staff1.id)]
        event.with_user(self.staff1).write({'state': 'cancelled'})
        messages = self.env['mail.message'].search([
            ('model', '=', 'sports.event'), ('res_id', '=', event.id),
        ])
        notices = messages.filtered(
            lambda m: self.staff1.partner_id in m.notified_partner_ids
        )
        self.assertTrue(notices, "sole-assignee cancel must still notify the canceller")

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_cancel_and_delete_without_staff_do_not_error(self):
        event = self._make_event(with_staff=False)
        event.action_cancel()
        self.assertEqual(event.state, 'cancelled')
        # And deletion of a staff-less event is also fine.
        event2 = self._make_event(with_staff=False, name='Empty 2')
        event2.unlink()
        self.assertFalse(event2.exists())
