# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWizards(TransactionCase):
    """Test UX wizards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_create_nolog=True))
        
        # Get lost message parent
        cls.lost_parent = cls.env['lost.message.parent'].search([], limit=1)
        if not cls.lost_parent:
            cls.lost_parent = cls.env['lost.message.parent'].create({})
        
        # Create test subcategory
        cls.subcategory = cls.env['lost.message.subcategory'].create({
            'name': 'Test',
            'code': 'test_wizard',
        })

    def _create_lost_message(self, subject='Test', body='Test body'):
        """Helper to create a lost message."""
        return self.env['mail.thread']._create_lost_message(
            body=body,
            body_is_html=False,
            subject=subject,
            model='lost.message.parent',
            res_id=self.lost_parent.id,
        )

    def test_categorize_wizard_single(self):
        """Categorize wizard assigns subcategory to single message."""
        message = self._create_lost_message()
        
        wizard = self.env['mail.message.categorize.wizard'].create({
            'message_ids': [(6, 0, [message.id])],
            'subcategory_id': self.subcategory.id,
        })
        wizard.action_categorize()
        
        self.assertEqual(message.lost_subcategory_id.id, self.subcategory.id)

    def test_categorize_wizard_batch(self):
        """Categorize wizard assigns subcategory to multiple messages."""
        messages = self.env['mail.message']
        for i in range(3):
            messages |= self._create_lost_message(subject=f'Test {i}')
        
        wizard = self.env['mail.message.categorize.wizard'].create({
            'message_ids': [(6, 0, messages.ids)],
            'subcategory_id': self.subcategory.id,
        })
        wizard.action_categorize()
        
        for msg in messages:
            self.assertEqual(msg.lost_subcategory_id.id, self.subcategory.id)

    def test_delete_wizard_count(self):
        """Delete wizard computes message count."""
        messages = self.env['mail.message']
        for i in range(5):
            messages |= self._create_lost_message()
        
        wizard = self.env['mail.message.delete.wizard'].create({
            'message_ids': [(6, 0, messages.ids)],
        })
        
        self.assertEqual(wizard.message_count, 5)

    def test_delete_wizard_action(self):
        """Delete wizard removes messages."""
        messages = self.env['mail.message']
        for i in range(3):
            messages |= self._create_lost_message()
        
        message_ids = messages.ids
        
        wizard = self.env['mail.message.delete.wizard'].create({
            'message_ids': [(6, 0, message_ids)],
        })
        wizard.action_delete()
        
        # Messages should be deleted
        remaining = self.env['mail.message'].search([('id', 'in', message_ids)])
        self.assertEqual(len(remaining), 0)

    def test_invalid_address_wizard_sender_info(self):
        """Invalid address wizard extracts sender info."""
        message = self.env['mail.thread']._create_lost_message(
            body='Test',
            body_is_html=False,
            subject='Test Subject',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
            email_from='"John Doe" <john@example.com>',
        )
        
        wizard = self.env['mail.invalid.address.wizard'].create({
            'message_id': message.id,
        })
        
        self.assertEqual(wizard.sender_email, '"John Doe" <john@example.com>')
        self.assertEqual(wizard.sender_name, 'John Doe')
        self.assertEqual(wizard.original_subject, 'Test Subject')

    def test_invalid_address_wizard_noreply_detection(self):
        """Invalid address wizard detects no-reply addresses."""
        message = self.env['mail.thread']._create_lost_message(
            body='Test',
            body_is_html=False,
            subject='Test',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
            email_from='noreply@example.com',
        )
        
        wizard = self.env['mail.invalid.address.wizard'].create({
            'message_id': message.id,
        })
        
        self.assertTrue(wizard.is_noreply)

    def test_invalid_address_wizard_regular_email(self):
        """Invalid address wizard doesn't flag regular emails."""
        message = self.env['mail.thread']._create_lost_message(
            body='Test',
            body_is_html=False,
            subject='Test',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
            email_from='john@example.com',
        )
        
        wizard = self.env['mail.invalid.address.wizard'].create({
            'message_id': message.id,
        })
        
        self.assertFalse(wizard.is_noreply)

    def test_finance_triage_wizard_has_helpdesk(self):
        """Finance triage wizard detects helpdesk module."""
        message = self._create_lost_message()
        
        wizard = self.env['mail.finance.triage.wizard'].create({
            'message_ids': [(6, 0, [message.id])],
        })
        
        # has_helpdesk should be False in test environment (no helpdesk installed)
        has_helpdesk = 'helpdesk.team' in self.env
        self.assertEqual(wizard.has_helpdesk, has_helpdesk)

    def test_action_categorize_returns_wizard(self):
        """action_categorize method returns wizard action."""
        message = self._create_lost_message()
        
        action = message.action_categorize()
        
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'mail.message.categorize.wizard')

    def test_action_batch_delete_returns_wizard(self):
        """action_batch_delete method returns wizard action."""
        message = self._create_lost_message()
        
        action = message.action_batch_delete()
        
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'mail.message.delete.wizard')

    def test_action_finance_triage_returns_wizard(self):
        """action_finance_triage method returns wizard action."""
        message = self._create_lost_message()
        
        action = message.action_finance_triage()
        
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'mail.finance.triage.wizard')

    def test_action_notify_invalid_address_returns_wizard(self):
        """action_notify_invalid_address method returns wizard action."""
        message = self._create_lost_message()
        
        action = message.action_notify_invalid_address()
        
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'mail.invalid.address.wizard')

    def test_extract_name_with_quotes(self):
        """_extract_name handles quoted name format."""
        wizard = self.env['mail.invalid.address.wizard'].new({})
        
        name = wizard._extract_name('"John Doe" <john@example.com>')
        self.assertEqual(name, 'John Doe')

    def test_extract_name_without_quotes(self):
        """_extract_name handles unquoted name format."""
        wizard = self.env['mail.invalid.address.wizard'].new({})
        
        name = wizard._extract_name('John Doe <john@example.com>')
        self.assertEqual(name, 'John Doe')

    def test_extract_name_email_only(self):
        """_extract_name extracts local part from email-only format."""
        wizard = self.env['mail.invalid.address.wizard'].new({})
        
        name = wizard._extract_name('john.doe@example.com')
        self.assertEqual(name, 'john.doe')

    def test_extract_name_empty(self):
        """_extract_name handles empty input."""
        wizard = self.env['mail.invalid.address.wizard'].new({})
        
        name = wizard._extract_name('')
        self.assertEqual(name, '')
        
        name = wizard._extract_name(None)
        self.assertEqual(name, '')

    def test_invalid_address_action_skip(self):
        """action_skip marks message with auto-reply subcategory."""
        message = self.env['mail.thread']._create_lost_message(
            body='Test',
            body_is_html=False,
            subject='Test',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
            email_from='noreply@example.com',
        )
        
        wizard = self.env['mail.invalid.address.wizard'].create({
            'message_id': message.id,
        })
        result = wizard.action_skip()
        
        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        # Check subcategory assigned if exists
        auto_reply_subcat = self.env.ref('mail_manual_routing_ux.subcategory_auto_reply', raise_if_not_found=False)
        if auto_reply_subcat:
            self.assertEqual(message.lost_subcategory_id.id, auto_reply_subcat.id)

    def test_invalid_address_action_send(self):
        """action_send_notification sends email and closes wizard."""
        message = self.env['mail.thread']._create_lost_message(
            body='Test',
            body_is_html=False,
            subject='Test Subject',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
            email_from='sender@example.com',
        )
        
        wizard = self.env['mail.invalid.address.wizard'].create({
            'message_id': message.id,
            'reply_subject': 'Re: Invalid address',
            'reply_body': '<p>Test reply</p>',
        })
        result = wizard.action_send_notification()
        
        self.assertEqual(result['type'], 'ir.actions.act_window_close')

    def test_finance_triage_forward(self):
        """_forward_messages forwards email correctly."""
        message = self._create_lost_message(subject='Invoice question')
        
        wizard = self.env['mail.finance.triage.wizard'].create({
            'message_ids': [(6, 0, [message.id])],
            'action': 'forward',
            'forward_email': 'finance@example.com',
        })
        result = wizard.action_triage()
        
        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        # Check subcategory assigned
        finance_subcat = self.env.ref('mail_manual_routing_ux.subcategory_finance', raise_if_not_found=False)
        if finance_subcat:
            self.assertEqual(message.lost_subcategory_id.id, finance_subcat.id)

    def test_finance_triage_forward_no_email(self):
        """_forward_messages does nothing without email."""
        message = self._create_lost_message()
        
        wizard = self.env['mail.finance.triage.wizard'].create({
            'message_ids': [(6, 0, [message.id])],
            'action': 'forward',
            'forward_email': False,
        })
        result = wizard.action_triage()
        
        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        # Message should not be categorized
        self.assertFalse(message.lost_subcategory_id)

    def test_noreply_detection_patterns(self):
        """_compute_is_noreply detects various no-reply patterns."""
        patterns = [
            ('noreply@example.com', True),
            ('no-reply@example.com', True),
            ('donotreply@example.com', True),
            ('do-not-reply@example.com', True),
            ('mailer-daemon@example.com', True),
            ('NOREPLY@EXAMPLE.COM', True),  # case insensitive
            ('support@example.com', False),
            ('info@example.com', False),
        ]
        
        for i, (email, expected) in enumerate(patterns):
            # Use unique content to avoid loop prevention
            message = self.env['mail.thread']._create_lost_message(
                body=f'Test content {i} for {email}',  # Unique content
                body_is_html=False,
                subject=f'Test {i} - {email}',  # Unique subject
                model='lost.message.parent',
                res_id=self.lost_parent.id,
                email_from=email,
            )
            wizard = self.env['mail.invalid.address.wizard'].create({
                'message_id': message.id,
            })
            self.assertEqual(
                wizard.is_noreply, expected,
                f"Expected is_noreply={expected} for {email}"
            )
