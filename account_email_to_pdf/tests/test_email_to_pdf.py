import base64
from odoo.tests.common import TransactionCase
from odoo.tools.misc import find_in_path


class TestHtmlToPdf(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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

    def test_html_to_pdf_with_complex_content(self):
        """Test HTML to PDF conversion with more complex content."""
        if not self.wkhtmltopdf_available:
            self.skipTest("wkhtmltopdf not available")

        # More complex HTML with tables and images
        complex_html = """
        <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    table { border-collapse: collapse; width: 100%; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #f2f2f2; }
                </style>
            </head>
            <body>
                <h1>Complex HTML Test</h1>
                <table>
                    <tr>
                        <th>Header 1</th>
                        <th>Header 2</th>
                        <th>Header 3</th>
                    </tr>
                    <tr>
                        <td>Row 1, Cell 1</td>
                        <td>Row 1, Cell 2</td>
                        <td>Row 1, Cell 3</td>
                    </tr>
                    <tr>
                        <td>Row 2, Cell 1</td>
                        <td>Row 2, Cell 2</td>
                        <td>Row 2, Cell 3</td>
                    </tr>
                </table>
            </body>
        </html>
        """

        # Convert complex HTML to PDF
        pdf_content = self.account_move._html_to_pdf(complex_html)

        # Verify the PDF was created
        self.assertTrue(
            pdf_content, "PDF content should be generated from complex HTML"
        )
        self.assertTrue(
            pdf_content.startswith(b"%PDF-"), "Content should be a valid PDF"
        )
        self.assertTrue(len(pdf_content) > 100, "PDF should have reasonable size")
