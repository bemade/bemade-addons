# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestThreading(TransactionCase):
    """Test threading preservation when routing lost messages."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_create_nolog=True))
        
        # Get or create the lost message parent
        cls.lost_parent = cls.env['lost.message.parent'].search([], limit=1)
        if not cls.lost_parent:
            cls.lost_parent = cls.env['lost.message.parent'].create({})
        
        # Create a partner for testing
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com',
        })

    def test_threading_headers_stored(self):
        """In-Reply-To and References headers should be stored."""
        in_reply_to = '<original-message-id@example.com>'
        references = '<first@example.com> <second@example.com>'
        
        message = self.env['mail.thread']._create_lost_message(
            body='Test body',
            body_is_html=False,
            subject='Test Threading',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
            in_reply_to=in_reply_to,
            references=references,
        )
        
        self.assertEqual(message.lost_in_reply_to, in_reply_to)
        self.assertEqual(message.lost_references, references)

    def test_threading_headers_empty(self):
        """Missing headers should result in empty fields."""
        message = self.env['mail.thread']._create_lost_message(
            body='Test body',
            body_is_html=False,
            subject='Test No Headers',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
        )
        
        self.assertFalse(message.lost_in_reply_to)
        self.assertFalse(message.lost_references)

    def test_routing_sets_lost_origin(self):
        """Routing a message should set lost_origin flag."""
        # Create a lost message
        message = self.env['mail.thread']._create_lost_message(
            body='Test body',
            body_is_html=False,
            subject='Test Routing',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
        )
        
        self.assertTrue(message.is_unattached)
        self.assertFalse(message.lost_origin)
        
        # Simulate routing via wizard
        wizard = self.env['mail.message.attach.wizard'].with_context(
            active_id=message.id
        ).create({
            'res_reference': f'res.partner,{self.partner.id}',
        })
        wizard.action_attach_mail_message()
        
        # Check message was routed
        self.assertFalse(message.is_unattached)
        self.assertTrue(message.lost_origin)
        self.assertEqual(message.model, 'res.partner')
        self.assertEqual(message.res_id, self.partner.id)

    def test_routing_finds_parent_via_in_reply_to(self):
        """Routing should find parent message via In-Reply-To header."""
        # Create an original message on the partner
        original_message_id = '<original-123@example.com>'
        original = self.env['mail.message'].create({
            'model': 'res.partner',
            'res_id': self.partner.id,
            'body': 'Original message',
            'message_id': original_message_id,
            'message_type': 'email',
        })
        
        # Create a lost message that replies to the original
        reply = self.env['mail.thread']._create_lost_message(
            body='Reply body',
            body_is_html=False,
            subject='Re: Test',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
            in_reply_to=original_message_id,
        )
        
        # Route the reply to the same partner
        wizard = self.env['mail.message.attach.wizard'].with_context(
            active_id=reply.id
        ).create({
            'res_reference': f'res.partner,{self.partner.id}',
        })
        wizard.action_attach_mail_message()
        
        # Reply should have original as parent
        self.assertEqual(reply.parent_id.id, original.id)

    def test_routing_finds_parent_via_references(self):
        """Routing should find parent message via References header."""
        # Create an original message on the partner
        original_message_id = '<original-456@example.com>'
        original = self.env['mail.message'].create({
            'model': 'res.partner',
            'res_id': self.partner.id,
            'body': 'Original message',
            'message_id': original_message_id,
            'message_type': 'email',
        })
        
        # Create a lost message with References (no In-Reply-To)
        # Note: References header contains message IDs in angle brackets
        reply = self.env['mail.thread']._create_lost_message(
            body='Reply body',
            body_is_html=False,
            subject='Re: Test',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
            references=f'<old@example.com> <original-456@example.com>',
        )
        
        # Route the reply to the same partner
        wizard = self.env['mail.message.attach.wizard'].with_context(
            active_id=reply.id
        ).create({
            'res_reference': f'res.partner,{self.partner.id}',
        })
        wizard.action_attach_mail_message()
        
        # Reply should have original as parent (found via References)
        self.assertEqual(reply.parent_id.id, original.id)

    def test_routing_no_parent_different_record(self):
        """Routing should not find parent if on different record."""
        # Create a message on partner
        original_message_id = '<original-789@example.com>'
        self.env['mail.message'].create({
            'model': 'res.partner',
            'res_id': self.partner.id,
            'body': 'Original message',
            'message_id': original_message_id,
            'message_type': 'email',
        })
        
        # Create another partner
        other_partner = self.env['res.partner'].create({
            'name': 'Other Partner',
        })
        
        # Create a lost message replying to original
        reply = self.env['mail.thread']._create_lost_message(
            body='Reply body',
            body_is_html=False,
            subject='Re: Test',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
            in_reply_to=original_message_id,
        )
        
        # Route to DIFFERENT partner
        wizard = self.env['mail.message.attach.wizard'].with_context(
            active_id=reply.id
        ).create({
            'res_reference': f'res.partner,{other_partner.id}',
        })
        wizard.action_attach_mail_message()
        
        # Reply should NOT have a parent (wrong record)
        self.assertFalse(reply.parent_id)

    def test_parse_reference_string_format(self):
        """_parse_reference should handle string format 'model,id'."""
        wizard = self.env['mail.message.attach.wizard'].create({})
        
        model, res_id = wizard._parse_reference('res.partner,123')
        self.assertEqual(model, 'res.partner')
        self.assertEqual(res_id, 123)

    def test_parse_reference_invalid_format(self):
        """_parse_reference should return None for invalid formats."""
        wizard = self.env['mail.message.attach.wizard'].create({})
        
        # No comma
        model, res_id = wizard._parse_reference('invalid')
        self.assertIsNone(model)
        self.assertIsNone(res_id)
        
        # Non-integer ID
        model, res_id = wizard._parse_reference('res.partner,abc')
        self.assertIsNone(model)
        self.assertIsNone(res_id)
        
        # Empty
        model, res_id = wizard._parse_reference(None)
        self.assertIsNone(model)
        self.assertIsNone(res_id)

    def test_extract_message_ids_multiple(self):
        """_extract_message_ids should extract all message IDs from References."""
        wizard = self.env['mail.message.attach.wizard'].create({})
        
        refs = '<first@example.com> <second@example.com> <third@example.com>'
        ids = wizard._extract_message_ids(refs)
        
        self.assertEqual(len(ids), 3)
        self.assertEqual(ids[0], '<first@example.com>')
        self.assertEqual(ids[2], '<third@example.com>')

    def test_extract_message_ids_empty(self):
        """_extract_message_ids should return empty list for None/empty."""
        wizard = self.env['mail.message.attach.wizard'].create({})
        
        self.assertEqual(wizard._extract_message_ids(None), [])
        self.assertEqual(wizard._extract_message_ids(''), [])

    def test_routing_without_threading_headers(self):
        """Routing message without threading headers should still work."""
        # Create a lost message without any threading headers
        message = self.env['mail.thread']._create_lost_message(
            body='No threading',
            body_is_html=False,
            subject='Test',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
        )
        
        # Route it
        wizard = self.env['mail.message.attach.wizard'].with_context(
            active_id=message.id
        ).create({
            'res_reference': f'res.partner,{self.partner.id}',
        })
        wizard.action_attach_mail_message()
        
        # Should be routed without parent
        self.assertFalse(message.is_unattached)
        self.assertTrue(message.lost_origin)
        self.assertFalse(message.parent_id)
