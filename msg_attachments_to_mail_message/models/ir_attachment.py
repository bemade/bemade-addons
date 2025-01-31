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
import psycopg2
import os
import shutil
from odoo.tools import config


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
            # Debug logging avant conversion
            _logger.info("=== DEBUG INFO AVANT CONVERSION [%s] ===", self.name)
            _logger.info("[%s] Type de msg_data: %s", self.name, type(msg_data))
            _logger.info("[%s] Attributs disponibles: %s", self.name,
                dir(msg_data) if hasattr(msg_data, '__dict__') else 'No attributes')
            
            # Ensure we have bytes
            if not isinstance(msg_data, bytes):
                _logger.info("[%s] Conversion nécessaire", self.name)
                if hasattr(msg_data, 'read'):
                    _logger.info("[%s] Conversion via read()", self.name)
                    msg_data = msg_data.read()
                elif isinstance(msg_data, str):
                    _logger.info("[%s] Conversion string vers bytes", self.name)
                    msg_data = msg_data.encode('utf-8')
                elif hasattr(msg_data, 'datas'):
                    _logger.info("[%s] Utilisation de l'attribut datas", self.name)
                    msg_data = base64.b64decode(msg_data.datas)
                else:
                    error_msg = f"Expected bytes-like object, got {type(msg_data)}"
                    _logger.error("[%s] %s", self.name, error_msg)
                    self._move_to_review_dir('msg_conversion')
                    raise ValueError(error_msg)

            # Debug logging après conversion
            _logger.info("=== DEBUG INFO APRÈS CONVERSION [%s] ===", self.name)
            _logger.info("[%s] Type final de msg_data: %s", self.name, type(msg_data))
            _logger.info("[%s] Taille des données: %d bytes", self.name, len(msg_data))
            
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

            # Get current record's partner if exists
            current_partner = False
            if self.res_model and self.res_id:
                try:
                    record = self.env[self.res_model].browse(self.res_id)
                    if hasattr(record, "partner_id"):
                        current_partner = record.partner_id
                except Exception as e:
                    _logger.warning("Failed to get current partner: %s", str(e))

            # Recherche du partenaire expéditeur avec gestion d'erreur
            from_partner = None
            if from_email:
                try:
                    with self.env.cr.savepoint():
                        from_partners = self.env["res.partner"].search([
                            ("email", "=ilike", from_email),
                            ("active", "in", [True, False])
                        ])
                        
                        if len(from_partners) == 1:
                            from_partner = from_partners[0]
                        elif len(from_partners) > 1 and current_partner:
                            # Search among contacts linked to the current object's company
                            company = current_partner.commercial_partner_id
                            company_contacts = from_partners.filtered(
                                lambda p: p.commercial_partner_id == company
                            )
                            if company_contacts:
                                from_partner = company_contacts[0]
                except Exception as e:
                    _logger.warning("Failed to process sender partner: %s", str(e))

            # Set email headers
            email_msg["Subject"] = self._clean_header_value(msg_file.subject)
            email_msg["From"] = self._clean_header_value(msg_file.sender)
            email_msg["To"] = self._clean_header_value(msg_file.to)
            if msg_file.cc:
                email_msg["Cc"] = self._clean_header_value(msg_file.cc)

            # Add email body
            if msg_file.body:
                body = html_sanitize(msg_file.body)
                email_msg.attach(MIMEText(body, "html"))

            # Process attachments
            for att in msg_file.attachments:
                try:
                    filename = att.longFilename or att.shortFilename
                    if filename:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(att.data)
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={filename}",
                        )
                        email_msg.attach(part)
                except Exception as e:
                    _logger.warning(
                        "Failed to process attachment %s: %s - Attachment data type: %s, Content: %s",
                        filename,
                        str(e),
                        type(att.data),
                        str(att.data)[:100] if att.data else "None"
                    )
                    # Move problematic attachment to review directory
                    self._move_to_review_dir('msg_conversion')

            return email_msg.as_string()

        except Exception as e:
            _logger.error("Error converting MSG to EML: %s", str(e))
            raise

    def _get_review_dir(self, error_type):
        """
        Get the review directory path.
        
        Args:
            error_type (str): Type of error encountered
            
        Returns:
            str: Path to the review directory
        """
        # Get Odoo's data directory
        data_dir = config.get('data_dir', os.path.dirname(self._full_path(self.store_fname)))
        
        # Create a specific directory for review files
        review_base = os.path.join(data_dir, 'review_files')
        
        # Create subdirectory for specific error type
        review_dir = os.path.join(review_base, error_type)
        
        return review_dir

    def _move_to_review_dir(self, error_type):
        """
        Move problematic files to a review directory.
        
        Args:
            error_type (str): Type of error encountered (e.g., 'pdf_page_count', 'msg_conversion')
        """
        self.ensure_one()
        try:
            if not self.store_fname:
                _logger.warning("[%s] No stored file to move", self.name or 'Unknown')
                return

            # Get review directory
            review_dir = self._get_review_dir(error_type)
            os.makedirs(review_dir, exist_ok=True)

            # Move file to review directory
            src_path = self._full_path(self.store_fname)
            if os.path.exists(src_path):
                # Create a subdirectory for the current date
                date_dir = os.path.join(review_dir, fields.Date.today().strftime('%Y%m%d'))
                os.makedirs(date_dir, exist_ok=True)
                
                # Add timestamp to filename to avoid conflicts
                timestamp = fields.Datetime.now().strftime('%H%M%S')
                filename = f"{timestamp}_{self.id}_{self.name}"
                dst_path = os.path.join(date_dir, filename)
                
                # Copy file instead of moving to preserve original
                shutil.copy2(src_path, dst_path)
                
                # Log the action
                _logger.info(
                    "File %s moved to review directory due to %s error. New location: %s",
                    self.name or 'Unknown', error_type, dst_path
                )
                
                # Update attachment record
                self.write({
                    'description': f"{self.description or ''}\nMoved to review directory due to {error_type} error on {fields.Datetime.now()}"
                })
                
        except Exception as e:
            _logger.error("[%s] Failed to move file to review directory: %s", self.name or 'Unknown', str(e))

    def process_msg_as_email(self):
        """
        Convert MSG file to EML and process it using Odoo's mail module.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.ensure_one()

            if not self._is_msg_file():
                _logger.warning("File is not a valid MSG file: %s", self.name)
                return False

            if not self.datas:
                _logger.warning("No data found in MSG file: %s", self.name)
                return False

            if self.msg_processed:
                _logger.debug("MSG file already processed: %s", self.name)
                return True

            try:
                # Convert base64 to bytes with validation
                msg_data = base64.b64decode(self.datas)
                if not isinstance(msg_data, bytes):
                    raise ValueError(f"Expected bytes after b64decode, got {type(msg_data)}")
                
                eml_content = self._msg_to_eml(msg_data)
                if not isinstance(eml_content, str):
                    raise ValueError(f"Expected string EML content, got {type(eml_content)}")

            except (ValueError, TypeError) as e:
                _logger.error("Data conversion error for %s: %s", self.name, str(e))
                return False

            if not eml_content:
                _logger.error("Failed to convert MSG to EML: %s", self.name)
                return False

            # Get thread model based on res_model
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
                "mail_create_skip_followers": True,
                "mail_auto_subscribe_no_notify": True,  # Prevent auto-subscription notifications
                "no_auto_thread": True  # Prevent automatic thread creation
            }

            try:
                with self.env.cr.savepoint():  # Use savepoint for transaction management
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

            except psycopg2.IntegrityError as e:
                if "mail_followers_mail_followers_res_partner_res_model_id_uniq" in str(e):
                    _logger.warning("Follower already exists, skipping: %s", str(e))
                    return thread_id if 'thread_id' in locals() else False
                raise

            except Exception as e:
                _logger.error("Error processing MSG file %s: %s", self.name, str(e), exc_info=True)
                if not self.env.context.get('skip_msg_processing_on_error'):
                    raise

            # Get error logging preference safely
            try:
                with self.env.cr.savepoint():
                    log_errors = self.env['ir.config_parameter'].sudo().get_param(
                        'msg_attachments.log_msg_error', 'False'
                    ).lower() == 'true'
            except Exception:
                log_errors = False  # Default to False if parameter can't be read

            # Si thread_id est False, on log l'erreur si configuré
            if log_errors:
                error_msg = f"Failed to process MSG file: {self.name} - message_process failed to create thread_id"
                _msg_import_logger.error(error_msg, exc_info=True)
            
            return False

        except Exception as e:
            if not self.env.context.get('skip_msg_processing_on_error'):
                raise

            # Log l'erreur si configuré
            log_errors = self.env['ir.config_parameter'].sudo().get_param(
                'msg_attachments.log_msg_error', 'False'
            ).lower() == 'true'
            
            if log_errors:
                error_msg = f"Error processing MSG file: {self.name} - {str(e)}"
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
        """Override create to handle problematic files."""
        if not isinstance(vals_list, list):
            vals_list = [vals_list]

        attachments = super().create(vals_list)
        
        for attachment in attachments:
            try:
                # Check if it's a PDF file
                if attachment.mimetype == 'application/pdf' and attachment.store_fname:
                    # Try to open and read the PDF
                    try:
                        import PyPDF2
                        with open(attachment._full_path(attachment.store_fname), 'rb') as pdf_file:
                            try:
                                pdf_reader = PyPDF2.PdfReader(pdf_file)
                                num_pages = len(pdf_reader.pages)
                                _logger.info("[%s] PDF processed successfully, pages: %d", attachment.name or 'Unknown', num_pages)
                            except Exception as e:
                                _logger.warning(
                                    "[%s] Failed to process PDF: %s", 
                                    attachment.name or 'Unknown', str(e)
                                )
                                attachment._move_to_review_dir('pdf_error')
                    except Exception as e:
                        _logger.error("[%s] Error accessing PDF file: %s", attachment.name or 'Unknown', str(e))
                
                # Process MSG files
                if attachment._is_msg_file():
                    attachment.process_msg_as_email()
            
            except Exception as e:
                _logger.error("[%s] Error processing attachment: %s", attachment.name or 'Unknown', str(e))

        return attachments

    def write(self, vals):
        """Override write to handle problematic files on update."""
        res = super().write(vals)
        
        if 'datas' in vals:
            for attachment in self:
                try:
                    # Check if it's a PDF file
                    if attachment.mimetype == 'application/pdf' and attachment.store_fname:
                        try:
                            import PyPDF2
                            with open(attachment._full_path(attachment.store_fname), 'rb') as pdf_file:
                                try:
                                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                                    num_pages = len(pdf_reader.pages)
                                    _logger.info("[%s] PDF processed successfully, pages: %d", attachment.name or 'Unknown', num_pages)
                                except Exception as e:
                                    _logger.warning(
                                        "[%s] Failed to process PDF: %s", 
                                        attachment.name or 'Unknown', str(e)
                                    )
                                    attachment._move_to_review_dir('pdf_error')
                        except Exception as e:
                            _logger.error("[%s] Error accessing PDF file: %s", attachment.name or 'Unknown', str(e))
                    
                    # Process MSG files
                    if attachment._is_msg_file():
                        attachment.process_msg_as_email()
                        
                except Exception as e:
                    _logger.error("[%s] Error processing attachment: %s", attachment.name or 'Unknown', str(e))
        
        return res
