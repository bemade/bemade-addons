# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHelpdeskIntegration(TransactionCase):
    """Test helpdesk integration for lost messages triage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_create_nolog=True))

        # Get lost message parent
        cls.lost_parent = cls.env['lost.message.parent'].search([], limit=1)
        if not cls.lost_parent:
            cls.lost_parent = cls.env['lost.message.parent'].create({})

        # Create helpdesk team
        cls.helpdesk_team = cls.env['helpdesk.team'].create({
            'name': 'Test Finance Team',
        })

    def _create_lost_message(self, subject='Test', body='Test body'):
        """Helper to create a lost message."""
        return self.env['mail.thread']._create_lost_message(
            body=body,
            body_is_html=False,
            subject=subject,
            model='lost.message.parent',
            res_id=self.lost_parent.id,
            email_from='sender@example.com',
        )

    def test_has_helpdesk_true(self):
        """has_helpdesk should be True when helpdesk is installed."""
        message = self._create_lost_message()

        wizard = self.env['mail.finance.triage.wizard'].create({
            'message_ids': [(6, 0, [message.id])],
        })

        self.assertTrue(wizard.has_helpdesk)

    def test_helpdesk_team_field_exists(self):
        """helpdesk_team_id field should exist on wizard."""
        message = self._create_lost_message()

        wizard = self.env['mail.finance.triage.wizard'].create({
            'message_ids': [(6, 0, [message.id])],
            'helpdesk_team_id': self.helpdesk_team.id,
        })

        self.assertEqual(wizard.helpdesk_team_id.id, self.helpdesk_team.id)

    def test_create_helpdesk_ticket_single(self):
        """_create_helpdesk_tickets creates a ticket for single message."""
        message = self._create_lost_message(subject='Invoice Question')

        wizard = self.env['mail.finance.triage.wizard'].create({
            'message_ids': [(6, 0, [message.id])],
            'action': 'helpdesk',
            'helpdesk_team_id': self.helpdesk_team.id,
        })
        result = wizard.action_triage()

        # Should return action to view ticket
        self.assertEqual(result['res_model'], 'helpdesk.ticket')
        self.assertTrue(result.get('res_id'))

        # Check ticket was created
        ticket = self.env['helpdesk.ticket'].browse(result['res_id'])
        self.assertEqual(ticket.name, 'Invoice Question')
        self.assertEqual(ticket.team_id.id, self.helpdesk_team.id)

    def test_create_helpdesk_tickets_batch(self):
        """_create_helpdesk_tickets creates tickets for multiple messages."""
        messages = self.env['mail.message']
        for i in range(3):
            messages |= self._create_lost_message(subject=f'Question {i}')

        wizard = self.env['mail.finance.triage.wizard'].create({
            'message_ids': [(6, 0, messages.ids)],
            'action': 'helpdesk',
            'helpdesk_team_id': self.helpdesk_team.id,
        })
        result = wizard.action_triage()

        # Should return action to view multiple tickets
        self.assertEqual(result['res_model'], 'helpdesk.ticket')
        self.assertIn('domain', result)

        # Check tickets were created
        tickets = self.env['helpdesk.ticket'].search(result['domain'])
        self.assertEqual(len(tickets), 3)

    def test_create_helpdesk_ticket_sets_subcategory(self):
        """Creating ticket should set finance subcategory on message."""
        message = self._create_lost_message()

        wizard = self.env['mail.finance.triage.wizard'].create({
            'message_ids': [(6, 0, [message.id])],
            'action': 'helpdesk',
            'helpdesk_team_id': self.helpdesk_team.id,
        })
        wizard.action_triage()

        finance_subcat = self.env.ref(
            'mail_manual_routing_ux.subcategory_finance',
            raise_if_not_found=False
        )
        if finance_subcat:
            self.assertEqual(message.lost_subcategory_id.id, finance_subcat.id)

    def test_create_helpdesk_ticket_no_team(self):
        """_create_helpdesk_tickets without team should just close."""
        message = self._create_lost_message()

        wizard = self.env['mail.finance.triage.wizard'].create({
            'message_ids': [(6, 0, [message.id])],
            'action': 'helpdesk',
            'helpdesk_team_id': False,
        })
        result = wizard.action_triage()

        self.assertEqual(result['type'], 'ir.actions.act_window_close')
