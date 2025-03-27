import base64
import logging
import os
import subprocess
import tempfile
from contextlib import closing
from datetime import datetime
from html import escape
import re

from odoo import models, fields
from odoo.tools.misc import find_in_path

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def message_new(self, msg_dict, custom_values={}):
        """Override to create a PDF attachment from the email content before processing.
        This ensures that emails without attachments can still be processed and converted to invoices.
        """
        # Get existing attachments in the email
        attachments = msg_dict.get("attachments", [])

        # Check if there are attachments that are not the .eml of the message itself
        regex = re.compile(r"^.*\.eml$", re.IGNORECASE)
        if len(attachments) > 1 or (len(attachments) == 1 and not regex.match(attachments[0][0])):
            return super().message_new(msg_dict, custom_values=custom_values)

        try:
            # Create a PDF from the email content
            pdf_attachment = self._create_pdf_from_email(msg_dict)
            if pdf_attachment:
                # Add the PDF to the message's attachments
                if not msg_dict.get("attachments"):
                    msg_dict["attachments"] = []

                # Convert the attachment to the format expected by mail_thread
                # Format: (name, base64_data, info_dict)
                attachment_data = (
                    pdf_attachment["name"],
                    pdf_attachment["datas"],
                    {"mimetype": "application/pdf"},
                )
                attachments.append(attachment_data)
        except Exception as e:
            _logger.exception("Error creating PDF from email: %s", e)
        return super().message_new(msg_dict, custom_values=custom_values)

    @classmethod
    def _html_to_pdf(cls, html_content):
        """Convert HTML content to PDF using wkhtmltopdf.

        Args:
            html_content (str): HTML content to convert to PDF

        Returns:
            bytes: PDF content as bytes or False if conversion failed
        """

        # Check if wkhtmltopdf is installed
        wkhtmltopdf_bin = find_in_path("wkhtmltopdf")
        if not wkhtmltopdf_bin:
            _logger.error("Cannot find wkhtmltopdf executable in system path")
            return False

        # Create temporary files for the HTML input and PDF output
        html_file_fd, html_file_path = tempfile.mkstemp(
            suffix=".html", prefix="email_to_pdf."
        )
        pdf_file_fd, pdf_file_path = tempfile.mkstemp(
            suffix=".pdf", prefix="email_to_pdf."
        )

        try:
            # Write the HTML content to the temporary file
            with closing(os.fdopen(html_file_fd, "wb")) as html_file:
                html_file.write(html_content.encode("utf-8"))

            # Close the PDF file descriptor as wkhtmltopdf will write to it
            os.close(pdf_file_fd)

            # Basic wkhtmltopdf command arguments
            command = [wkhtmltopdf_bin]
            command.extend(["--encoding", "utf-8"])
            command.extend(["--page-size", "A4"])
            command.extend(["--margin-top", "10mm"])
            command.extend(["--margin-bottom", "10mm"])
            command.extend(["--margin-left", "10mm"])
            command.extend(["--margin-right", "10mm"])
            command.append(html_file_path)
            command.append(pdf_file_path)

            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            _, err = process.communicate()

            if process.returncode != 0:
                _logger.error(
                    "wkhtmltopdf failed with error code %s: %s", process.returncode, err
                )
                return False

            # Read the generated PDF
            try:
                with open(pdf_file_path, "rb") as pdf_file:
                    pdf_content = pdf_file.read()

                return pdf_content
            except Exception as e:
                _logger.exception("Error reading generated PDF file: %s", e)
                return False

        except Exception as e:
            _logger.exception("Error during PDF generation: %s", e)
            return False

        finally:
            # Clean up temporary files
            try:
                os.unlink(html_file_path)
                os.unlink(pdf_file_path)
            except (OSError, IOError):
                _logger.error("Failed to remove temporary files")

    def _create_pdf_from_email(self, message_dict):
        """Create a PDF attachment from an email message.

        Args:
            message_dict (dict): Email message dictionary

        Returns:
            dict: Dictionary with keys `name` and `datas` containing the name and
                  base64 encoded data of the attachment
        """
        # Extract email details
        email_from = message_dict.get("email_from", "Unknown Sender")
        email_date = message_dict.get("date", datetime.now())
        subject = message_dict.get("subject", "No Subject")
        body = message_dict.get("body", "")

        # Format the date if it's a datetime object
        if isinstance(email_date, datetime):
            email_date = email_date.strftime("%Y-%m-%d %H:%M:%S")

        # Check if body is empty or None
        if not body:
            _logger.warning("Email body is empty, using placeholder content")
            body = "<p>This email did not contain any body content.</p>"

        # Create HTML content for the PDF
        html_content = f"""
        <html>
            <head>
                <meta charset="UTF-8">
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
        pdf_content = self._html_to_pdf(html_content)
        if not pdf_content:
            return False

        # Create a proper ir.attachment record
        filename = f"Email_{subject.replace(' ', '_')[:30]}.pdf"

        attachment = {
            "name": filename,
            "datas": base64.b64encode(pdf_content),
        }

        return attachment
