import base64
import logging
from datetime import datetime
from email.utils import formatdate
from html import escape

from odoo import models, fields
from odoo.tools.pdf import html_to_pdf

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _check_and_decode_attachment(self, attachments):
        """Override to convert email message to PDF if no attachments are present."""
        if not attachments or self.env.context.get('no_new_invoice'):
            # Original code would return False here, causing email rejection
            # Instead, we'll create a PDF from the email message
            message_dict = self.env.context.get('message_dict', {})
            if message_dict:
                try:
                    # Create a PDF from the email content
                    pdf_attachment = self._create_pdf_from_email(message_dict)
                    if pdf_attachment:
                        # Add the PDF to the attachments list
                        return super()._check_and_decode_attachment([pdf_attachment])
                except Exception as e:
                    _logger.exception("Error creating PDF from email: %s", e)
            
            # If we couldn't create a PDF, fall back to original behavior
            return False
        
        # If there are attachments, proceed with the original method
        return super()._check_and_decode_attachment(attachments)
    
    def _create_pdf_from_email(self, message_dict):
        """Create a PDF attachment from an email message."""
        # Extract email details
        email_from = message_dict.get('email_from', 'Unknown Sender')
        email_date = message_dict.get('date', datetime.now())
        subject = message_dict.get('subject', 'No Subject')
        body = message_dict.get('body', '')
        
        # Format the date if it's a datetime object
        if isinstance(email_date, datetime):
            email_date = email_date.strftime('%Y-%m-%d %H:%M:%S')
        
        # Create HTML content for the PDF
        html_content = f"""
        <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .email-header {{ border-bottom: 1px solid #ccc; padding-bottom: 10px; margin-bottom: 20px; }}
                    .email-meta {{ color: #666; font-size: 0.9em; margin-bottom: 5px; }}
                    .email-subject {{ font-size: 1.2em; font-weight: bold; margin-bottom: 15px; }}
                    .email-body {{ line-height: 1.5; }}
                </style>
            </head>
            <body>
                <div class="email-header">
                    <div class="email-meta">From: {escape(email_from)}</div>
                    <div class="email-meta">Date: {escape(email_date)}</div>
                    <div class="email-subject">{escape(subject)}</div>
                </div>
                <div class="email-body">
                    {body}
                </div>
            </body>
        </html>
        """
        
        # Convert HTML to PDF
        pdf_content = html_to_pdf(html_content)
        
        # Create attachment tuple (filename, content, mime_type)
        filename = f"Email_{subject.replace(' ', '_')[:30]}.pdf"
        attachment = (
            filename,
            base64.b64encode(pdf_content).decode('utf-8'),
            'application/pdf'
        )
        
        _logger.info("Created PDF attachment from email: %s", filename)
        return attachment
