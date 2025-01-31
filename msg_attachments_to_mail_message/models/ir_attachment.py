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
import time
import random
import socket
import tempfile


_logger = logging.getLogger(__name__)

_msg_import_logger = logging.getLogger("msg.import")
handler = logging.FileHandler("/var/log/odoo/msg_import.log")
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
_msg_import_logger.addHandler(handler)
_msg_import_logger.setLevel(logging.ERROR)

class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    # Cache au niveau de la classe
    _msg_conversion_cache = {}

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

    def _detect_encoding(self, data):
        """
        Detect the encoding of the data.
        
        Args:
            data (bytes): Data to analyze
            
        Returns:
            str: Detected encoding (e.g., 'utf-8', 'iso-8859-1', etc.)
        """
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result['encoding'] if result and result['encoding'] else 'utf-8'
            _logger.debug("Detected encoding: %s with confidence: %s", 
                         encoding, result.get('confidence', 0))
            return encoding
        except ImportError:
            _logger.info("chardet not installed, defaulting to utf-8")
            return 'utf-8'
        except Exception as e:
            _logger.warning("Error detecting encoding: %s", str(e))
            return 'utf-8'

    def _retry_operation(self, operation, max_retries=3, delay=1):
        """
        Retry an operation with exponential backoff.
        
        Args:
            operation (callable): Function to retry
            max_retries (int): Maximum number of retry attempts
            delay (int): Initial delay between retries in seconds
            
        Returns:
            Any: Result of the operation
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                return operation()
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    sleep_time = delay * (2 ** attempt)  # Exponential backoff
                    _logger.warning(
                        "Operation failed (attempt %d/%d): %s. Retrying in %d seconds...",
                        attempt + 1, max_retries, str(e), sleep_time
                    )
                    time.sleep(sleep_time)
                else:
                    _logger.error(
                        "Operation failed after %d attempts: %s",
                        max_retries, str(e)
                    )
        raise last_error

    def _get_cache_key(self, data):
        """
        Generate a cache key for the data.
        
        Args:
            data (bytes): Data to generate key for
            
        Returns:
            str: Cache key
        """
        import hashlib
        return hashlib.sha256(data).hexdigest()

    @api.model
    def _get_conversion_cache(self):
        """
        Get the conversion cache.
        
        Returns:
            dict: Conversion cache
        """
        return self._msg_conversion_cache

    def _cached_msg_to_eml(self, msg_data):
        """
        Cached version of MSG to EML conversion.
        
        Args:
            msg_data (bytes): MSG file data
            
        Returns:
            str: EML file data
        """
        cache = self._get_conversion_cache()
        cache_key = self._get_cache_key(msg_data)
        
        if cache_key in cache:
            _logger.debug("Using cached conversion result")
            return cache[cache_key]
            
        result = self._msg_to_eml(msg_data)
        cache[cache_key] = result
        return result

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
                    if not filename:
                        _logger.info("Skipping attachment with no filename")
                        continue

                    _logger.info("=== Processing attachment: %s ===", filename)
                    _logger.info("Attachment type: %s", type(att.data).__name__)
                    _logger.info("Attachment size: %d bytes", len(att.data) if hasattr(att.data, '__len__') else -1)

                    # Check if attachment is an email file (MSG or EML)
                    if isinstance(att.data, extract_msg.msg_classes.message.Message):
                        _logger.info("Processing as MSG file: %s", filename)
                        _logger.info("MSG attributes: %s", dir(att.data))
                        mime_type = "application/vnd.ms-outlook"
                    elif filename.lower().endswith('.eml'):
                        _logger.info("Processing as EML file: %s", filename)
                        mime_type = "message/rfc822"
                    else:
                        # Regular attachment
                        _logger.info("Processing as regular attachment: %s", filename)
                        _logger.info("Content type: %s", getattr(att, 'content_type', 'unknown'))
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(att.data)
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={filename}",
                        )
                        email_msg.attach(part)
                        _logger.info("Regular attachment processed successfully")
                        continue

                    # Process email file (MSG or EML)
                    _logger.info("Creating MIME part with type: %s", mime_type)
                    maintype, subtype = mime_type.split('/')
                    part = MIMEBase(maintype, subtype)
                    
                    # Get the raw data
                    if isinstance(att.data, extract_msg.msg_classes.message.Message):
                        _logger.info("Extracting raw bytes from MSG")
                        try:
                            # Try to get raw data using asEmailMessage
                            _logger.info("Converting MSG to email message")
                            email_message = att.data.asEmailMessage()
                            raw_data = email_message.as_bytes()
                            _logger.info("Successfully converted MSG to email message: %d bytes", len(raw_data))
                        except Exception as e:
                            _logger.warning("Failed to convert MSG to email message: %s", str(e))
                            try:
                                # Try to export as bytes
                                _logger.info("Trying to export MSG as bytes")
                                raw_data = att.data.exportBytes()
                                _logger.info("Successfully exported MSG as bytes: %d bytes", len(raw_data))
                            except Exception as e:
                                _logger.warning("Failed to export MSG as bytes: %s", str(e))
                                # Last resort: try to get the raw data directly
                                if hasattr(att.data, '_raw'):
                                    _logger.info("Using _raw attribute")
                                    raw_data = att.data._raw
                                else:
                                    _logger.warning("Could not get raw data from MSG, skipping attachment")
                                    continue
                    else:
                        _logger.info("Using raw data directly for EML")
                        raw_data = att.data
                    
                    if raw_data:
                        _logger.info("Raw data size: %d bytes", len(raw_data) if raw_data else 0)
                        
                        # Check if the data is base64 encoded
                        try:
                            # Try to decode base64 if it looks like base64
                            if isinstance(raw_data, str) and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in raw_data):
                                _logger.info("Data appears to be base64 encoded, decoding...")
                                import base64
                                raw_data = base64.b64decode(raw_data)
                                _logger.info("Successfully decoded base64 data: %d bytes", len(raw_data))
                        except Exception as e:
                            _logger.warning("Failed to decode base64 data: %s", str(e))
                        
                        # Set the payload and encode
                        part.set_payload(raw_data)
                        _logger.info("Encoding attachment in base64")
                        encoders.encode_base64(part)
                        
                        # Add headers
                        _logger.info("Adding headers to MIME part")
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={filename}",
                        )
                        part.add_header(
                            "Content-Type",
                            mime_type,
                            name=filename
                        )
                        
                        _logger.info("Attaching processed email file to message")
                        email_msg.attach(part)
                        _logger.info("=== Finished processing %s ===", filename)
                    else:
                        _logger.warning("No raw data available for %s, skipping", filename)
                    
                except Exception as e:
                    _logger.warning(
                        "Failed to process attachment %s: %s - Attachment data type: %s, Content: %s",
                        filename,
                        str(e),
                        type(att.data),
                        str(att.data)[:100] if att.data else "None",
                        exc_info=True
                    )
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

            def convert_msg():
                msg_data = base64.b64decode(self.datas)
                if not isinstance(msg_data, bytes):
                    raise ValueError(f"Expected bytes after b64decode, got {type(msg_data)}")
                
                # Use cached conversion
                eml_content = self._cached_msg_to_eml(msg_data)
                if not isinstance(eml_content, str):
                    raise ValueError(f"Expected string EML content, got {type(eml_content)}")
                return eml_content

            try:
                # Use retry mechanism for conversion
                eml_content = self._retry_operation(convert_msg)
            except Exception as e:
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

    @api.model
    def process_msg_attachments_batch(self, attachment_ids, batch_size=10):
        """
        Process multiple MSG attachments in batches.
        
        Args:
            attachment_ids (list): List of attachment IDs to process
            batch_size (int): Number of attachments to process in each batch
            
        Returns:
            dict: Processing results
        """
        results = {'success': [], 'failed': []}
        attachments = self.browse(attachment_ids)
        
        for i in range(0, len(attachments), batch_size):
            batch = attachments[i:i + batch_size]
            for attachment in batch:
                try:
                    if attachment.process_msg_as_email():
                        results['success'].append(attachment.id)
                    else:
                        results['failed'].append(attachment.id)
                except Exception as e:
                    _logger.error(
                        "Error processing attachment %s: %s",
                        attachment.name, str(e)
                    )
                    results['failed'].append(attachment.id)
                    
        return results
