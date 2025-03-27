from odoo.tests.common import TransactionCase
from odoo.tools.misc import find_in_path
from datetime import datetime



class TestHtmlToPdf(TransactionCase):
    """
    Test the functionality of converting an email to a PDF when it's received for a supplier invoice.

    This test simulates the full flow of an email being received through
    the mail alias and verifies that an account move is created with a PDF
    attachment generated from the email content.

    It's important to also run the tests in account, which can be done using the test tag:

    `/account:TestAccountIncomingSupplierInvoice.test_extend_with_attachments_document_formats`

    This specific test ensures we are not creating more attachments than necessary.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set up sender and alias for testing
        cls.sender_email = "sender@example.com"
        cls.alias_email = "test-invoices@example.com"

        # Check if wkhtmltopdf is available
        cls.wkhtmltopdf_available = bool(find_in_path("wkhtmltopdf"))

        # Get the model class to access the classmethod
        cls.account_move = cls.env["account.move"]

        # Simple test HTML content
        cls.test_html = """
        <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    h1 { color: #333; }
                </style>
            </head>
            <body>
                <h1>Test HTML Document</h1>
                <p>This is a test paragraph with <b>bold text</b> and <i>italic text</i>.</p>
                <ul>
                    <li>List item 1</li>
                    <li>List item 2</li>
                    <li>List item 3</li>
                </ul>
            </body>
        </html>
        """

        # Set up a supplier for testing
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Test Supplier",
                "email": cls.sender_email,
            }
        )

        # Set up a journal for incoming invoices
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase")], limit=1
        )

        # Set up the mail alias domain

        cls.alias_domain = cls.env["mail.alias.domain"].create({"name": "example.com"})
        # Set up a mail alias for the journal
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": cls.alias_email,
                "alias_model_id": cls.env["ir.model"]
                .search([("model", "=", "account.move")], limit=1)
                .id,
                "alias_domain_id": cls.alias_domain.id,
                "alias_defaults": f'{{"move_type": "in_invoice", "journal_id": {cls.journal.id}}}',
            }
        )
        cls.journal.alias_id = cls.alias

    def test_html_to_pdf_conversion(self):
        """Test the direct HTML to PDF conversion."""
        if not self.wkhtmltopdf_available:
            self.skipTest("wkhtmltopdf not available")

        # Call the method to convert HTML to PDF
        pdf_content = self.account_move._html_to_pdf(self.test_html)

        # Verify the PDF was created
        self.assertTrue(pdf_content, "PDF content should be generated")

        # Verify it's a valid PDF
        self.assertTrue(
            pdf_content.startswith(b"%PDF-"), "Content should be a valid PDF"
        )
        self.assertTrue(len(pdf_content) > 100, "PDF should have reasonable size")

    # Integration test
    def test_account_email_to_pdf_full_flow(self):
        """Test that an email without attachments is correctly converted to PDF
        and an account move is created.

        This test simulates the full flow of an email being received through
        the mail alias and verifies that an account move is created with a PDF
        attachment generated from the email content.
        """

        # Get the current timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        message_id = f"<test123_{timestamp}@example.com>"
        subject = f"Invoice from Test Supplier {timestamp}"
        date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

        # HTML body of the email
        html_body = "<html><body><h1>Invoice Test</h1><p>This is a test invoice from Test Supplier.</p><p>Amount: $100.00</p><p>Date: 2025-03-27</p></body></html>"

        # Construct the raw email with proper headers
        # Make sure the From header is correctly formatted for Odoo to parse
        raw_email = f"""Return-Path: <{self.sender_email}>
X-Original-To: {self.alias_email}
Delivered-To: {self.alias_email}
Received: from mail.example.com (mail.example.com [192.168.1.1])
From: {self.sender_email}
To: {self.alias_email}
Subject: {subject}
Date: {date}
Message-ID: {message_id}
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8
Content-Transfer-Encoding: 7bit

{html_body}"""

        # Process the email through the mail gateway
        # This simulates what happens when fetchmail receives an email
        invoice_count_before = self.env["account.move"].search_count(
            [("move_type", "=", "in_invoice")]
        )

        # Process the email through the mail gateway
        # We need to specify the model explicitly since we're in a test environment
        # In production, the alias would determine this automatically
        self.env["mail.thread"].with_context(fetchmail_server_id=1).message_process(
            model=None,
            message=raw_email,
            save_original=True,
            strip_attachments=False,
        )

        # Count account moves after the test
        # Note: move_type is the correct field name in Odoo, even if the linter doesn't recognize it
        move_count_after = self.env["account.move"].search_count(
            [("move_type", "=", "in_invoice")]
        )
        self.assertEqual(
            move_count_after,
            invoice_count_before + 1,
            "A new account move should be created",
        )

        # Find the newly created invoice
        invoice = self.env["account.move"].search(
            [("move_type", "=", "in_invoice")], order="id desc", limit=1
        )
        self.assertTrue(invoice, "An account move should be created")

        messages = invoice.message_ids
        self.assertEqual(len(messages), 1, "The account move should have one message")

        attachment = messages.attachment_ids

        self.assertTrue(attachment, "The message should have an attachment")

        attachment = attachment.filtered(
            lambda a: a.mimetype == "application/pdf" or ".pdf" in a.name
        )
        self.assertTrue(attachment, "The message should have a PDF attachment")

        # Verify the invoice is linked to the correct supplier
        self.assertEqual(
            invoice.partner_id,
            self.supplier,
            "The invoice should be linked to the correct supplier",
        )

        # Verify the invoice type
        self.assertEqual(
            invoice.move_type, "in_invoice", "The invoice should be an incoming invoice"
        )
