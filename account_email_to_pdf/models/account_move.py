import base64
import logging
import os
import subprocess
import tempfile
from contextlib import closing
from datetime import datetime
from html import escape
import re

from odoo import models, api
from odoo.tools.misc import find_in_path

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _routing_check_route(self, message, message_dict, route, raise_exception=True):
        """Override to create a PDF attachment from the email content before checking the route.
        The standard Odoo behavior bounces emails without attachments, but we want to
        process them by generating a PDF from the email content.
        """
        if route[0] == "account.move" and (
            len(message_dict.get("attachments", [])) < 1
            or message_dict["attachments"][0][0].lower().endswith(".eml")
        ):
            try:
                # Create a PDF from the email content
                pdf_attachment = self._create_pdf_from_email(message_dict)
                if pdf_attachment:
                    # Add the PDF to the message's attachments
                    if not message_dict.get("attachments"):
                        message_dict["attachments"] = []

                    # Convert the attachment to the format expected by mail_thread
                    # Format: (name, base64_data, info_dict)
                    attachment_data = (
                        pdf_attachment["name"],
                        pdf_attachment["datas"],
                        {"mimetype": "application/pdf"},
                    )
                    message_dict["attachments"].append(attachment_data)
            except Exception as e:
                _logger.exception(
                    "Error creating PDF from email in _routing_check_route: %s", e
                )

        return super()._routing_check_route(
            message, message_dict, route, raise_exception=raise_exception
        )

    @classmethod
    def _html_to_pdf(cls, html_content):
        """Convert HTML content to PDF using wkhtmltopdf.

        Args:
            html_content (str): HTML content to convert to PDF

        Returns:
            bytes: PDF content as bytes or False if conversion failed
        """
        # Check if the content is plain text (not HTML)
        # More comprehensive check for HTML content
        is_html = bool(re.search(r"<html", html_content, re.IGNORECASE))
        _logger.info(f"Input content length: {len(html_content)}")
        _logger.info(f"Is content already HTML? {is_html}")

        if not is_html:
            _logger.info(
                "Content appears to be plain text or not a complete HTML document, wrapping in HTML tags"
            )
            # Escape the content if it's not already HTML
            escaped_content = escape(html_content)
            _logger.info(f"Escaped content length: {len(escaped_content)}")

            # Wrap the content in basic HTML structure with proper styling for plain text
            html_content = f"""
            <!DOCTYPE html>
            <html>
                <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        pre {{ white-space: pre-wrap; font-family: monospace; background-color: #f9f9f9; padding: 10px; }}
                    </style>
                </head>
                <body>
                    <pre>{escaped_content}</pre>
                </body>
            </html>
            """
            _logger.info(f"Wrapped HTML content length: {len(html_content)}")

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
                encoded_content = html_content.encode("utf-8")
                _logger.info(f"Encoded HTML content length: {len(encoded_content)}")
                html_file.write(encoded_content)

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

            _logger.info(f"Running wkhtmltopdf command: {' '.join(command)}")
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            out, err = process.communicate()

            if process.returncode != 0:
                _logger.error(
                    "wkhtmltopdf failed with error code %s: %s", process.returncode, err
                )
                if out:
                    _logger.info(
                        f"wkhtmltopdf stdout: {out.decode('utf-8', errors='replace')[:200]}"
                    )
                if err:
                    _logger.error(
                        f"wkhtmltopdf stderr: {err.decode('utf-8', errors='replace')}"
                    )
                return False

            # Read the generated PDF
            try:
                with open(pdf_file_path, "rb") as pdf_file:
                    pdf_content = pdf_file.read()

                _logger.info(
                    f"Successfully read PDF file, size: {len(pdf_content)} bytes"
                )
                if pdf_content:
                    _logger.info(f"PDF file starts with: {pdf_content[:20]}")

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
        # Log message dict keys for debugging
        _logger.info(f"Message dict keys: {list(message_dict.keys())}")
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

        # Check if the body is plain text based on content-type
        # The content type can be found in the message headers or directly in the message_dict
        content_type = ""

        # Try to get content type from various places in the message dict
        if "content-type" in message_dict:
            content_type = message_dict["content-type"].lower()
            _logger.info(f"Found content-type directly in message_dict: {content_type}")

        # Try to get from headers
        headers = message_dict.get("headers", {})
        _logger.info(f"Headers type: {type(headers)}")

        if not content_type and headers:
            if isinstance(headers, dict):
                content_type = headers.get("Content-Type", "").lower()
                _logger.info(f"Found Content-Type in headers dict: {content_type}")
            elif isinstance(headers, list):
                _logger.info(f"Headers is a list with {len(headers)} items")
                for header in headers:
                    _logger.info(f"Header item: {header}")
                    if (
                        isinstance(header, tuple)
                        and len(header) >= 2
                        and header[0].lower() == "content-type"
                    ):
                        content_type = header[1].lower()
                        _logger.info(
                            f"Found Content-Type in headers list: {content_type}"
                        )
                        break

        # Try to determine from the body content if we still don't have a content type
        if not content_type:
            if re.search(r"<html", body, re.IGNORECASE):
                content_type = "text/html"
                _logger.info("Determined content type as HTML from body content")
            else:
                content_type = "text/plain"
                _logger.info("Defaulting to plain text content type")

        _logger.info(f"Final email content type determination: {content_type}")

        # Convert plain text to HTML if needed
        if "text/plain" in content_type:
            _logger.info("Converting plain text email body to HTML")
            # Replace newlines with <br> tags and wrap in paragraph tags
            # Escape HTML special characters to prevent injection
            body = f"<div style='white-space: pre-wrap; font-family: monospace;'>{escape(body)}</div>"
            _logger.info(f"Converted plain text body length: {len(body)}")
            _logger.info(f"First 100 chars of converted body: {body[:100]}")

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
        _logger.info(f"HTML content length before PDF conversion: {len(html_content)}")
        _logger.info(f"First 200 chars of HTML content: {html_content[:200]}")

        pdf_content = self._html_to_pdf(html_content)

        if pdf_content:
            _logger.info(f"PDF generation successful, size: {len(pdf_content)} bytes")
            _logger.info(f"PDF starts with: {pdf_content[:20]}")
        else:
            _logger.error("PDF generation failed")
            return False

        # Create a proper ir.attachment record
        filename = f"Email_{subject.replace(' ', '_')[:30]}.pdf"

        # Note: No need to base64 encode the PDF content here
        # When this attachment is added to message_dict["attachments"], Odoo expects raw binary data
        # Odoo will handle the base64 encoding when creating the actual ir.attachment record
        _logger.info(f"Raw PDF length: {len(pdf_content)} bytes")

        attachment = {
            "name": filename,
            "datas": pdf_content,
        }

        return attachment
