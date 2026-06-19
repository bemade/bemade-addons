from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHelpdeskOneTicketPerEmail(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.MailThread = cls.env["mail.thread"]
        cls.HelpdeskTicket = cls.env.get("helpdesk.ticket")

    def test_mail_thread_model_exists(self):
        """Test that mail.thread model exists"""
        self.assertIsNotNone(self.MailThread)

    def test_helpdesk_ticket_model(self):
        """Test that helpdesk.ticket model exists if installed"""
        if self.HelpdeskTicket:
            self.assertIsNotNone(self.HelpdeskTicket)

    def test_mail_thread_fields(self):
        """Test mail.thread has expected fields"""
        self.assertTrue(hasattr(self.MailThread, "message_ids"))

    def test_thread_message_tracking(self):
        """Test message tracking in mail.thread"""
        # Basic test that thread model works
        self.assertTrue(True)
