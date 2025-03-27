import base64
from odoo.tests.common import TransactionCase
from odoo.tools.misc import find_in_path
from unittest.mock import patch


class TestEmailProcessing(TransactionCase):
    """Integration tests for email processing with PDF generation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Check if wkhtmltopdf is available
        cls.wkhtmltopdf_available = bool(find_in_path("wkhtmltopdf"))

        # Get the model class to access the methods
        cls.account_move = cls.env["account.move"]

    def test_create_pdf_from_email(self):
        """Test that an email without attachments can be converted to PDF.

        This test directly verifies that the _create_pdf_from_email method
        correctly generates a PDF attachment from an email message without
        attachments, allowing the invoice creation process to continue.
        """
        if not self.wkhtmltopdf_available:
            self.skipTest("wkhtmltopdf not available")

        # Create a sample email message dictionary (similar to what would be parsed from an email)
        message_dict = {
            "subject": "Test Invoice",
            "from": "test@example.com",
            "to": "invoices@example.com",
            "body": "<html><body><h1>Invoice Test</h1><p>This is a test invoice.</p></body></html>",
            "attachments": [],  # No attachments
            "message_id": "<test123@example.com>",
        }

        # Call the method directly to create a PDF from the email
        attachment = self.account_move._create_pdf_from_email(message_dict)

        # Verify that an attachment was created
        self.assertTrue(attachment, "An attachment should have been created")
        # The actual name format is 'Email_' + subject + '.pdf' with spaces replaced by underscores
        self.assertEqual(
            attachment.name,
            "Email_Test_Invoice.pdf",
            "Attachment name should match expected format",
        )
        self.assertEqual(
            attachment.mimetype, "application/pdf", "Attachment should be a PDF"
        )

        # Verify the content of the PDF attachment
        pdf_data = base64.b64decode(attachment.datas)
        self.assertTrue(pdf_data.startswith(b"%PDF-"), "Content should be a valid PDF")
        self.assertTrue(len(pdf_data) > 100, "PDF should have a reasonable size")

    def test_check_and_decode_attachment_with_empty_attachments(self):
        """Test that _check_and_decode_attachment doesn't reject emails with no attachments."""
        if not self.wkhtmltopdf_available:
            self.skipTest("wkhtmltopdf not available")

        # Set up a context with a message_dict to simulate email processing
        message_dict = {
            "subject": "Test Invoice",
            "from": "test@example.com",
            "to": "invoices@example.com",
            "body": "<html><body><h1>Invoice Test</h1><p>This is a test invoice.</p></body></html>",
            "attachments": [],  # No attachments
            "message_id": "<test123@example.com>",
        }

        # Call the method with an empty attachments list
        # We need to pass the message_dict in the context so _create_pdf_from_email can access it
        result = self.account_move.with_context(
            message_dict=message_dict
        )._check_and_decode_attachment([])

        # Verify that the result is not False (which would mean email rejection)
        self.assertNotEqual(
            result,
            False,
            "Should not reject the email when no attachments are provided",
        )

        # Verify that the result contains attachment data
        self.assertTrue(result, "Should return attachment data")
