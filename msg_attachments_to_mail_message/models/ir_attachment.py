"""This module extends ir.attachment model to handle MSG file attachments.

It provides functionality to convert MSG files (Outlook messages) to EML format
and process them as regular email messages in Odoo. This includes extracting
attachments, handling headers, and creating proper mail.message records.
"""

from odoo import models, api, fields
from odoo.tools import html_sanitize
import base64
import logging
from odoo.tools.translate import _
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
import re
from odoo.tools import email_normalize, email_split
from io import BytesIO
import extract_msg


_logger = logging.getLogger(__name__)

_msg_import_logger = logging.getLogger("msg.import")
handler = logging.FileHandler("/var/log/odoo/msg_import.log")
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
_msg_import_logger.addHandler(handler)
_msg_import_logger.setLevel(logging.ERROR)

class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    msg_processed = fields.Boolean(string="MSG Processed", default=False)
    mail_message_id = fields.Many2one("mail.message", string="Created Mail Message")

    def _is_msg_file(self):
        """
        Check if the attachment is an MSG file and validate size.

        Returns:
            bool: True if the attachment is an MSG file, False otherwise.
        """
        self.ensure_one()

        # Check if it's an MSG file
        is_msg = self.with_context().sudo().mimetype in ['application/vnd.ms-outlook', 'application/x-ole-storage'] or (
            self.name and self.name.lower().endswith(".msg")
        )

        if not is_msg:
            return False

        # Check file size
        max_size = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("msg_attachments.max_file_size") or 25
        )
        file_size_mb = (
            len(self.datas) * 3 / 4 / 1024 / 1024
        )  # Convert from base64 to MB

        if file_size_mb > max_size:
            log_errors = self.env['ir.config_parameter'].sudo().get_param('msg_attachments.log_msg_error', 'False').lower() == 'true'
            log_file = self.env['ir.config_parameter'].sudo().get_param('msg_attachments.log_file_path')
            error_msg = f"File size error for {self.name}: File size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({max_size} MB)"
            if log_errors and log_file:
                _msg_import_logger.error(error_msg)
            self._notify_error(
                "File Size Error",
                _("The MSG file is too large. Maximum allowed size is %s MB")
                % max_size,
            )
            return False

        return True

    def _clean_header_value(self, value):
        """
        Clean header value by removing line breaks and extra whitespace.

        Args:
            value (str): Header value to clean.

        Returns:
            str: Cleaned header value.
        """
        if not value:
            return ""
        # Replace any combination of whitespace (including newlines) with a single space
        return " ".join(str(value).split())

    def _msg_to_eml(self, msg_data):
        """
        Convert MSG file data to EML format.

        Args:
            msg_data (bytes): MSG file data.

        Returns:
            str: EML file data.
        """
        try:
            # Read the MSG file
            msg_file = extract_msg.Message(BytesIO(msg_data))
            _logger.debug(
                "Converting MSG to EML - Subject: %s, From: %s, To: %s",
                msg_file.subject,
                msg_file.sender,
                msg_file.to,
            )

            # Create email message
            email_msg = MIMEMultipart("related")

            # Clean and normalize email addresses
            from_email = email_normalize(msg_file.sender) if msg_file.sender else False
            to_emails = email_split(msg_file.to) if msg_file.to else []
            cc_emails = email_split(msg_file.cc) if msg_file.cc else []

            # Vérifier si les adresses existent dans les partenaires
            partner_model = self.env["res.partner"]
            from_partners = (
                partner_model.search([("email", "=ilike", from_email)])
                if from_email
                else False
            )

            # Get current record's partner if exists
            current_partner = False
            if self.res_model and self.res_id:
                record = self.env[self.res_model].browse(self.res_id)
                if hasattr(record, "partner_id"):
                    current_partner = record.partner_id

            if not from_partners:
                if current_partner and from_email:
                    # Create new contact under the parent company
                    company = current_partner.commercial_partner_id
                    # Extract name from email if possible
                    display_name = msg_file.sender
                    if "<" in display_name and ">" in display_name:
                        display_name = display_name.split("<")[0].strip()

                    from_partner = partner_model.create(
                        {
                            "name": display_name,
                            "email": from_email,
                            "parent_id": company.id,
                            "company_id": (
                                company.company_id.id
                                if company.company_id
                                else self.env.company.id
                            ),
                            "type": "contact",
                        }
                    )
                    _logger.info(
                        "Created new contact %s under company %s for email %s",
                        display_name,
                        company.name,
                        from_email,
                    )
                else:
                    _logger.warning(
                        "Email sender not found in partners and no current partner to link to: %s",
                        from_email,
                    )
                    # Continue processing with the original sender
                    from_partner = None
            elif len(from_partners) > 1:
                if current_partner:
                    # Search among contacts linked to the current object's company
                    company = current_partner.commercial_partner_id
                    company_contacts = from_partners.filtered(
                        lambda p: p.commercial_partner_id == company
                    )

                    if company_contacts:
                        # Si on trouve des contacts liés à la compagnie, prendre le plus récent
                        from_partner = (
                            company_contacts.filtered("active").sorted(
                                "write_date", reverse=True
                            )[0]
                            if company_contacts.filtered("active")
                            else company_contacts[0]
                        )
                        _logger.info(
                            "Plusieurs partenaires trouvés pour l'email %s - Utilisation du contact %s lié à la compagnie %s",
                            from_email,
                            from_partner.name,
                            company.name,
                        )
                    else:
                        # Si aucun contact lié à la compagnie n'est trouvé, utiliser la logique précédente
                        company_partner = from_partners.filtered("is_company")
                        if len(company_partner) == 1:
                            from_partner = company_partner
                        else:
                            from_partner = (
                                from_partners.filtered("active").sorted(
                                    "write_date", reverse=True
                                )[0]
                                if from_partners.filtered("active")
                                else from_partners[0]
                            )
                        _logger.info(
                            "Plusieurs partenaires trouvés pour l'email %s - Utilisation de %s (aucun contact lié à la compagnie actuelle)",
                            from_email,
                            from_partner.name,
                        )
                else:
                    # Si pas de partenaire courant, utiliser la logique précédente
                    company_partner = from_partners.filtered("is_company")
                    if len(company_partner) == 1:
                        from_partner = company_partner
                    else:
                        from_partner = (
                            from_partners.filtered("active").sorted(
                                "write_date", reverse=True
                            )[0]
                            if from_partners.filtered("active")
                            else from_partners[0]
                        )
                    _logger.info(
                        "Plusieurs partenaires trouvés pour l'email %s - Utilisation de %s",
                        from_email,
                        from_partner.name,
                    )
            else:
                from_partner = from_partners

            # Add headers
            email_msg["Subject"] = (
                self._clean_header_value(msg_file.subject) or "No Subject"
            )
            email_msg["From"] = self._clean_header_value(msg_file.sender)
            email_msg["To"] = self._clean_header_value(msg_file.to)
            email_msg["Cc"] = (
                self._clean_header_value(msg_file.cc) if msg_file.cc else None
            )
            email_msg["Date"] = (
                msg_file.date.strftime("%a, %d %b %Y %H:%M:%S %z")
                if msg_file.date
                else formatdate(localtime=True)
            )

            # Add original MSG headers if present
            for header in ["Message-ID", "In-Reply-To", "References"]:
                if header.lower() in msg_file.header:
                    header_value = self._clean_header_value(
                        msg_file.header[header.lower()]
                    )
                    if header_value:  # Only add header if it has a value
                        email_msg[header] = header_value

            # Set the body
            if msg_file.body:
                body = msg_file.body

                # Check if metadata should be included
                show_metadata = (
                    self.env["ir.config_parameter"]
                    .sudo()
                    .get_param("msg_attachments.format_metadata", "True")
                    .lower()
                    == "true"
                )

                if show_metadata:
                    # Format the metadata section
                    metadata_html = f"""
                        <div style="background-color: #f8f9fa; padding: 10px; margin-bottom: 15px; border: 1px solid #dee2e6; border-radius: 4px; font-family: Arial, sans-serif; font-size: 13px;">
                            <div style="font-weight: bold; color: #495057; margin-bottom: 8px;">Original Email Details:</div>
                            <table style="border-collapse: collapse; width: 100%;">
                                <tr>
                                    <td style="padding: 2px 8px 2px 0; color: #495057; width: 100px;"><strong>From:</strong></td>
                                    <td style="padding: 2px 0;">{html_sanitize(msg_file.sender or "")}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 2px 8px 2px 0; color: #495057;"><strong>Date:</strong></td>
                                    <td style="padding: 2px 0;">{msg_file.date.strftime("%Y-%m-%d %H:%M:%S") if msg_file.date else "Unknown"}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 2px 8px 2px 0; color: #495057;"><strong>To:</strong></td>
                                    <td style="padding: 2px 0;">{html_sanitize(msg_file.to or "")}</td>
                                </tr>
                    """

                    if msg_file.cc:
                        metadata_html += f"""
                                <tr>
                                    <td style="padding: 2px 8px 2px 0; color: #495057;"><strong>CC:</strong></td>
                                    <td style="padding: 2px 0;">{html_sanitize(msg_file.cc)}</td>
                                </tr>
                        """

                    if "message-id" in msg_file.header:
                        metadata_html += f"""
                                <tr>
                                    <td style="padding: 2px 8px 2px 0; color: #495057;"><strong>Message-ID:</strong></td>
                                    <td style="padding: 2px 0; word-break: break-all;">{html_sanitize(msg_file.header["message-id"])}</td>
                                </tr>
                        """

                    metadata_html += """
                            </table>
                        </div>
                    """

                # Check if the body is HTML or contains HTML-like content
                is_html = "<html" in body.lower() or any(
                    tag in body.lower() for tag in ["<div", "<p", "<br", "<table", "<a"]
                )

                if not is_html:
                    # Convert plain text to HTML
                    body = body.replace("\n", "<br>")
                    # Convert URLs to links
                    body = re.sub(
                        r'(https?://[^\s<>"]+|www\.[^\s<>"]+)',
                        r'<a href="\1">\1</a>',
                        body,
                    )
                    # Convert CID references to img tags
                    if "[cid:" in body:
                        body = re.sub(
                            r"\[cid:([^\]]+)\]",
                            lambda m: f'<img src="cid:{m.group(1)}" alt="{m.group(1)}">',
                            body,
                        )
                    # Wrap in HTML tags
                    body = f'<div style="font-family: Arial, sans-serif; font-size: 13px;">{body}</div>'

                if show_metadata:
                    # Add metadata at the top
                    body = metadata_html + body

                # Always sanitize HTML
                body = html_sanitize(
                    body, sanitize_tags=False, sanitize_attributes=False, sanitize_style=False
                )

                html_part = MIMEText(body, "html")
                email_msg.attach(html_part)
            else:
                html_part = MIMEText("", "html")
                email_msg.attach(html_part)

            # Add attachments
            for attachment in msg_file.attachments:
                if not hasattr(attachment, "data") or not attachment.data:
                    continue

                try:
                    filename = attachment.getFilename()
                except AttributeError:
                    filename = "unknown.bin"
                    _logger.warning(
                        "Could not get filename for attachment, using default: %s",
                        filename,
                    )

                if hasattr(attachment, "contentId") and attachment.contentId:
                    # Image avec CID - utiliser MIMEImage
                    maintype, subtype = (attachment.mimetype or "image/jpeg").split(
                        "/", 1
                    )
                    if maintype == "image":
                        mime_part = MIMEImage(attachment.data, _subtype=subtype)
                        mime_part.add_header(
                            "Content-ID", f"<{attachment.contentId.strip('<>')}>"
                        )
                        mime_part.add_header(
                            "Content-Disposition", "inline", filename=filename
                        )
                        _logger.debug(
                            "Adding inline image with CID: %s, filename: %s",
                            attachment.contentId,
                            filename,
                        )
                    else:
                        # Fallback pour les non-images avec CID
                        mime_part = MIMEBase(maintype, subtype)
                        mime_part.set_payload(attachment.data)
                        encoders.encode_base64(mime_part)
                        mime_part.add_header(
                            "Content-ID", f"<{attachment.contentId.strip('<>')}>"
                        )
                        mime_part.add_header(
                            "Content-Disposition", "inline", filename=filename
                        )
                else:
                    # Pièce jointe normale
                    maintype, subtype = (
                        attachment.mimetype or "application/octet-stream"
                    ).split("/", 1)
                    mime_part = MIMEBase(maintype, subtype)
                    mime_part.set_payload(attachment.data)
                    encoders.encode_base64(mime_part)
                    mime_part.add_header(
                        "Content-Disposition", "attachment", filename=filename
                    )

                email_msg.attach(mime_part)

            return email_msg.as_string()

        except Exception as e:
            _msg_import_logger.error(
                "Error converting MSG to EML: %s", str(e), exc_info=True
            )
            raise

    def process_msg_as_email(self):
        """
        Convert MSG file to EML and process it using Odoo's mail module.

        Returns:
            bool: True if successful, False otherwise
        """
        self.ensure_one()
        _logger.debug(
            "Starting MSG processing for file: %s (model: %s, res_id: %s)",
            self.name,
            self.res_model,
            self.res_id,
        )

        if not self._is_msg_file():
            log_errors = self.env['ir.config_parameter'].sudo().get_param('msg_attachments.log_msg_error', 'False').lower() == 'true'
            log_file = self.env['ir.config_parameter'].sudo().get_param('msg_attachments.log_file_path')
            error_msg = f"Invalid MSG file: {self.name} (model: {self.res_model}, res_id: {self.res_id})"
            if log_errors and log_file:
                _msg_import_logger.error(error_msg)
            self._notify_error(
                "Invalid File", _("The selected file is not a valid MSG file")
            )
            return False

        try:
            # Convert MSG to EML
            msg_data = base64.b64decode(self.datas)
            eml_content = self._msg_to_eml(msg_data)

            # Process using Odoo's standard mail handling
            thread_model = (
                self.env[self.res_model] if self.res_model else self.env["mail.thread"]
            )
            _logger.debug("Using thread model: %s", thread_model._name)

            # Set context for message creation
            context = {
                "default_model": self.res_model,
                "default_res_id": self.res_id,
                "mail_create_nosubscribe": True,
                "mail_create_nolog": True,
                "mail_notify_force_send": False,
                "mail_create_force_model": self.res_model,
                "mail_thread_quote": False,
            }

            # Process the EML using Odoo's standard message_process
            thread_id = thread_model.with_context(**context).message_process(
                model=self.res_model,
                message=eml_content,
                custom_values={
                    "res_id": self.res_id,
                    "model": self.res_model,
                    "msg_attachment_id": self.id,
                },
                thread_id=self.res_id,
            )

            if thread_id:
                _logger.debug(
                    "Message processed successfully, thread_id: %s", thread_id
                )
                self.write(
                    {
                        "description": _("Processed as email on %s")
                        % fields.Datetime.now(),
                        "msg_processed": True,
                    }
                )
                return thread_id
            else:
                log_errors = self.env['ir.config_parameter'].sudo().get_param('msg_attachments.log_msg_error', 'False').lower() == 'true'
                log_file = self.env['ir.config_parameter'].sudo().get_param('msg_attachments.log_file_path')
                error_msg = f"Failed to process MSG file: {self.name} - message_process failed to create thread_id"
                _msg_import_logger.error(error_msg, exc_info=True)
                return False

        except Exception as e:
            log_errors = self.env['ir.config_parameter'].sudo().get_param('msg_attachments.log_msg_error', 'False').lower() == 'true'
            log_file = self.env['ir.config_parameter'].sudo().get_param('msg_attachments.log_file_path')
            error_msg = f"Error processing MSG file: {self.name} - {str(e)}"
            if log_errors and log_file:
                _msg_import_logger.error(error_msg, exc_info=True)
            self._notify_error(
                "Processing Error", _("Could not process the MSG file: %s") % str(e)
            )
            return False

    def _notify_error(self, title, message):
        """
        Show error notification to the user.

        Args:
            title (str): Title of the notification.
            message (str): Message to display in the notification.

        Returns:
            None
        """
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "notification",
            {
                "type": "danger",
                "title": title,
                "message": message,
                "sticky": True,
            },
        )

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super().create(vals_list)
        for attachment in attachments:
            if attachment._is_msg_file():
                attachment.process_msg_as_email()
        return attachments
