# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHtmlEscaping(TransactionCase):
    """Test HTML escaping fix in _create_lost_message."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_create_nolog=True))
        # Get or create the lost message parent
        cls.lost_parent = cls.env['lost.message.parent'].search([], limit=1)
        if not cls.lost_parent:
            cls.lost_parent = cls.env['lost.message.parent'].create({})

    def test_html_body_preserved(self):
        """HTML body should not be double-escaped."""
        html_body = '<p>Hello <strong>World</strong></p>'
        
        message = self.env['mail.thread']._create_lost_message(
            body=html_body,
            body_is_html=True,
            subject='Test HTML',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
        )
        
        # Body should contain the HTML tags, not escaped versions
        self.assertIn('<p>', message.body)
        self.assertIn('<strong>', message.body)
        self.assertNotIn('&lt;p&gt;', message.body)
        self.assertNotIn('&lt;strong&gt;', message.body)

    def test_plain_text_converted(self):
        """Plain text body should be converted to HTML."""
        plain_body = 'Hello\nWorld'
        
        message = self.env['mail.thread']._create_lost_message(
            body=plain_body,
            body_is_html=False,
            subject='Test Plain',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
        )
        
        # Body should be wrapped in HTML tags
        self.assertIn('<p>', message.body)
        # Newline should be converted to <br>
        self.assertIn('<br>', message.body)

    def test_markup_not_double_escaped(self):
        """Markup objects should not be double-escaped."""
        html_body = Markup('<p>Already safe</p>')
        
        message = self.env['mail.thread']._create_lost_message(
            body=html_body,
            body_is_html=True,
            subject='Test Markup',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
        )
        
        self.assertIn('<p>', message.body)
        self.assertNotIn('&lt;p&gt;', message.body)

    def test_special_characters_in_html(self):
        """Special characters in HTML should be preserved correctly."""
        html_body = '<p>Price: 100€ &amp; tax included</p>'
        
        message = self.env['mail.thread']._create_lost_message(
            body=html_body,
            body_is_html=True,
            subject='Test Special Chars',
            model='lost.message.parent',
            res_id=self.lost_parent.id,
        )
        
        # HTML entities should be preserved
        self.assertIn('100€', message.body)
        self.assertIn('&amp;', message.body)
