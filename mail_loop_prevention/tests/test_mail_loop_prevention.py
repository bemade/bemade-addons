# Copyright 2025 DurPro
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta
from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMailLoopPrevention(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "test@example.com",
            }
        )
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.Settings = cls.env["res.config.settings"]

    def setUp(self):
        super().setUp()
        # Reset config to defaults for each test
        self.ICP.set_param("mail_loop_prevention.enabled", "True")
        self.ICP.set_param("mail_loop_prevention.time_window_hours", "48")
        self.ICP.set_param("mail_loop_prevention.max_identical_messages", "3")

    def test_normal_messages_not_blocked(self):
        """Test that normal user comments are never blocked."""
        # Post the same message multiple times as a comment
        for i in range(5):
            msg = self.partner.message_post(
                body="<p>This is a test message</p>",
                subject="Test Subject",
                message_type="comment",
            )
            self.assertTrue(msg, f"Message {i+1} should not be blocked")

    def test_auto_reply_loop_detected(self):
        """Test that auto-reply loops are detected and blocked."""
        auto_reply_body = "<p>Thank you for your message. We will respond shortly.</p>"
        auto_reply_subject = "Auto-Reply: Message Received"

        # Post the same auto-reply 3 times (should succeed)
        for i in range(3):
            msg = self.partner.message_post(
                body=auto_reply_body,
                subject=auto_reply_subject,
                message_type="notification",
            )
            self.assertTrue(msg, f"Auto-reply {i+1} should be posted")

        # The 4th identical message should be blocked
        initial_count = len(self.partner.message_ids)
        msg = self.partner.message_post(
            body=auto_reply_body,
            subject=auto_reply_subject,
            message_type="notification",
        )
        # Message count should not increase
        self.assertEqual(
            len(self.partner.message_ids),
            initial_count,
            "4th identical message should be blocked",
        )

    def test_time_window_expiry(self):
        """Test that old messages outside time window don't count."""
        auto_reply_body = "<p>Automated response</p>"

        # Post 3 messages at different times
        with freeze_time("2025-01-01 00:00:00"):
            self.partner.message_post(
                body=auto_reply_body,
                message_type="notification",
            )

        with freeze_time("2025-01-02 00:00:00"):
            self.partner.message_post(
                body=auto_reply_body,
                message_type="notification",
            )

        # 50 hours later (outside 48-hour window), the first message shouldn't count
        with freeze_time("2025-01-03 02:00:00"):
            # These should succeed because first message is outside window
            for i in range(3):
                msg = self.partner.message_post(
                    body=auto_reply_body,
                    message_type="notification",
                )
                self.assertTrue(msg, f"Message {i+1} should not be blocked")

    def test_different_content_not_blocked(self):
        """Test that different messages are not blocked."""
        # Post 5 different auto-replies
        for i in range(5):
            msg = self.partner.message_post(
                body=f"<p>Auto-reply message {i}</p>",
                message_type="notification",
            )
            self.assertTrue(msg, f"Different message {i+1} should not be blocked")

    def test_identical_messages_blocked(self):
        """Test that identical messages are blocked."""
        # Post the exact same message multiple times
        message_body = "<p>Thank you for your message</p>"

        # Post first 3 (should succeed)
        for i in range(3):
            msg = self.partner.message_post(
                body=message_body,
                message_type="notification",
            )
            self.assertTrue(msg, f"Message {i+1} should be posted")

        # 4th identical message should be blocked
        initial_count = len(self.partner.message_ids)
        self.partner.message_post(
            body=message_body,
            message_type="notification",
        )
        self.assertEqual(
            len(self.partner.message_ids),
            initial_count,
            "4th identical message should be blocked",
        )

    def test_config_disabled(self):
        """Test that loop prevention can be disabled."""
        self.ICP.set_param("mail_loop_prevention.enabled", "False")

        auto_reply_body = "<p>Auto-reply</p>"

        # Post 5 identical messages - none should be blocked when disabled
        for i in range(5):
            msg = self.partner.message_post(
                body=auto_reply_body,
                message_type="notification",
            )
            self.assertTrue(msg, f"Message {i+1} should not be blocked when disabled")

    def test_custom_threshold(self):
        """Test that custom threshold is respected."""
        # Set threshold to 2 instead of 3
        self.ICP.set_param("mail_loop_prevention.max_identical_messages", "2")

        auto_reply_body = "<p>Auto-reply</p>"

        # Post 2 messages (should succeed)
        for i in range(2):
            msg = self.partner.message_post(
                body=auto_reply_body,
                message_type="notification",
            )
            self.assertTrue(msg, f"Message {i+1} should be posted")

        # 3rd should be blocked with threshold of 2
        initial_count = len(self.partner.message_ids)
        self.partner.message_post(
            body=auto_reply_body,
            message_type="notification",
        )
        self.assertEqual(
            len(self.partner.message_ids),
            initial_count,
            "3rd message should be blocked with threshold of 2",
        )

    def test_email_message_type_checked(self):
        """Test that email message type is also checked for loops."""
        email_body = "<p>Delivery notification</p>"

        # Post 3 identical emails
        for i in range(3):
            msg = self.partner.message_post(
                body=email_body,
                message_type="email",
            )
            self.assertTrue(msg, f"Email {i+1} should be posted")

        # 4th should be blocked
        initial_count = len(self.partner.message_ids)
        self.partner.message_post(
            body=email_body,
            message_type="email",
        )
        self.assertEqual(
            len(self.partner.message_ids),
            initial_count,
            "4th identical email should be blocked",
        )

    def test_config_validation_invalid_time_window(self):
        """Test that invalid time_window_hours values are rejected."""
        # Test too low
        with self.assertRaises(ValidationError):
            settings = self.Settings.create(
                {
                    "mail_loop_prevention_time_window_hours": 0,
                }
            )
            settings.execute()

        with self.assertRaises(ValidationError):
            settings = self.Settings.create(
                {
                    "mail_loop_prevention_time_window_hours": -5,
                }
            )
            settings.execute()

        # Test too high
        with self.assertRaises(ValidationError):
            settings = self.Settings.create(
                {
                    "mail_loop_prevention_time_window_hours": 1000,
                }
            )
            settings.execute()

    def test_config_validation_invalid_max_messages(self):
        """Test that invalid max_identical_messages values are rejected."""
        # Test too low
        with self.assertRaises(ValidationError):
            settings = self.Settings.create(
                {
                    "mail_loop_prevention_max_identical_messages": 1,
                }
            )
            settings.execute()

        with self.assertRaises(ValidationError):
            settings = self.Settings.create(
                {
                    "mail_loop_prevention_max_identical_messages": 0,
                }
            )
            settings.execute()

        # Test too high
        with self.assertRaises(ValidationError):
            settings = self.Settings.create(
                {
                    "mail_loop_prevention_max_identical_messages": 200,
                }
            )
            settings.execute()

    def test_config_validation_valid_boundary_values(self):
        """Test that valid boundary values are accepted."""
        # Test minimum valid values
        settings = self.Settings.create(
            {
                "mail_loop_prevention_time_window_hours": 1,
                "mail_loop_prevention_max_identical_messages": 2,
            }
        )
        settings.execute()
        self.assertEqual(
            self.ICP.get_param("mail_loop_prevention.time_window_hours"), "1"
        )
        self.assertEqual(
            self.ICP.get_param("mail_loop_prevention.max_identical_messages"), "2"
        )

        # Test maximum valid values
        settings = self.Settings.create(
            {
                "mail_loop_prevention_time_window_hours": 720,
                "mail_loop_prevention_max_identical_messages": 100,
            }
        )
        settings.execute()
        self.assertEqual(
            self.ICP.get_param("mail_loop_prevention.time_window_hours"), "720"
        )
        self.assertEqual(
            self.ICP.get_param("mail_loop_prevention.max_identical_messages"), "100"
        )

    def test_config_validation_enabled_param(self):
        """Test that enabled parameter can be toggled."""
        # Test enabling
        settings = self.Settings.create(
            {
                "mail_loop_prevention_enabled": True,
            }
        )
        settings.execute()
        self.assertTrue(
            self.Settings._get_param_as_bool("mail_loop_prevention.enabled")
        )

        # Test disabling
        settings = self.Settings.create(
            {
                "mail_loop_prevention_enabled": False,
            }
        )
        settings.execute()
        self.assertFalse(
            self.Settings._get_param_as_bool("mail_loop_prevention.enabled")
        )
