from odoo import models, api, fields
from odoo.tools import html_sanitize
import extract_msg
import base64
import logging
from odoo.tools.translate import _
from email.message import EmailMessage
import lxml.html
import re
from odoo.tools import email_normalize, email_split

_logger = logging.getLogger(__name__)

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    msg_processed = fields.Boolean(string='MSG Processed', default=False)
    mail_message_id = fields.Many2one('mail.message', string='Created Mail Message')

    def _is_msg_file(self):
        """Check if the attachment is an MSG file and validate size."""
        self.ensure_one()
        
        # Check if it's an MSG file
        is_msg = (
            self.mimetype == 'application/vnd.ms-outlook' or
            (self.name and self.name.lower().endswith('.msg'))
        )
        
        if not is_msg:
            return False

        # Check file size
        max_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'msg_attachments.max_file_size', '25'))
        file_size_mb = len(self.datas) * 3 / 4 / 1024 / 1024  # Convert from base64 to MB
        
        if file_size_mb > max_size:
            self._notify_error('File Size Error', 
                _('The MSG file is too large. Maximum allowed size is %s MB') % max_size)
            return False
        
        return True

    def _clean_header_value(self, value):
        """Clean header value by removing line breaks and extra whitespace."""
        if not value:
            return ''
        # Replace any combination of whitespace (including newlines) with a single space
        return ' '.join(str(value).split())

    def process_msg_as_email(self):
        """Convert MSG file to RFC822 email format and process it using Odoo's mail module."""
        self.ensure_one()
        _logger.info('Starting MSG processing for file: %s (model: %s, res_id: %s)', 
                    self.name, self.res_model, self.res_id)

        if not self._is_msg_file():
            _logger.warning('File %s is not a valid MSG file', self.name)
            self._notify_error('Invalid File', 
                _('The selected file is not a valid MSG file'))
            return False

        try:
            # Read the MSG file
            _logger.info('Decoding MSG file data')
            msg_data = base64.b64decode(self.datas)
            msg_file = extract_msg.Message(msg_data)
            _logger.info('MSG file info - Subject: %s, From: %s, To: %s', 
                        msg_file.subject, msg_file.sender, msg_file.to)
            
            # Convert MSG to email format
            email_msg = EmailMessage()
            
            # Add headers
            email_msg['Subject'] = self._clean_header_value(msg_file.subject) or _("No Subject")
            email_msg['From'] = self._clean_header_value(msg_file.sender)
            email_msg['To'] = self._clean_header_value(msg_file.to)
            email_msg['Cc'] = self._clean_header_value(msg_file.cc)
            email_msg['Date'] = msg_file.date.strftime('%a, %d %b %Y %H:%M:%S %z') if msg_file.date else formatdate(localtime=True)
            
            # Add original MSG headers if present
            for header in ['Message-ID', 'In-Reply-To', 'References']:
                if header.lower() in msg_file.header:
                    email_msg[header] = self._clean_header_value(msg_file.header[header.lower()])
            
            # Set the body
            if msg_file.body:
                _logger.info('Processing message body')
                body = msg_file.body
                # Convert [cid:xxx] to proper HTML img tags if needed
                cid_pattern = r'\[cid:([^\]]+)\]'
                body = re.sub(cid_pattern, r'<img src="cid:\1">', body)
                # Clean HTML if needed
                if '<html' in body.lower():
                    body = html_sanitize(body)
                email_msg.set_content(body, subtype='html')
            else:
                _logger.warning('No message body found')
                email_msg.set_content('', subtype='html')
            
            # Add attachments
            _logger.info('Processing %d attachments', len(msg_file.attachments))
            for attachment in msg_file.attachments:
                if not hasattr(attachment, 'data') or not attachment.data:
                    continue
                
                try:
                    filename = attachment.getFilename()
                except AttributeError:
                    filename = 'unknown.bin'
                    _logger.warning('Could not get filename for attachment, using default: %s', filename)
                
                maintype, subtype = (attachment.mimetype or 'application/octet-stream').split('/', 1)
                
                headers = {}
                if hasattr(attachment, 'content_id') and attachment.content_id:
                    cid = attachment.content_id.strip('<>')
                    headers['Content-ID'] = f'<{cid}>'
                
                email_msg.add_attachment(
                    attachment.data,
                    maintype=maintype,
                    subtype=subtype,
                    filename=filename,
                    headers=headers
                )
            
            # Process using Odoo's standard mail handling
            thread_model = self.env[self.res_model] if self.res_model else self.env['mail.thread']
            _logger.info('Using thread model: %s', thread_model._name)
            
            # Set context for message creation
            context = {
                'default_model': self.res_model,
                'default_res_id': self.res_id,
                'mail_create_nosubscribe': True,
                'mail_create_nolog': True,
                'mail_notify_force_send': False,
                'mail_create_force_model': self.res_model,
                'mail_thread_quote': False,
            }
            
            # Process the email using Odoo's standard message_process
            thread_id = thread_model.with_context(**context).message_process(
                model=self.res_model,
                message=email_msg.as_bytes(),
                custom_values={
                    'res_id': self.res_id,
                    'model': self.res_model,
                    'msg_attachment_id': self.id,
                },
                thread_id=self.res_id
            )
            
            if thread_id:
                _logger.info('Message processed successfully, thread_id: %s', thread_id)
                # Mark MSG as processed
                self.write({
                    'description': _('Processed as email on %s') % fields.Datetime.now(),
                    'msg_processed': True,
                })
                return thread_id
            else:
                _logger.error('message_process failed to create thread_id')
                return False

        except Exception as e:
            _logger.error('Error processing MSG file %s: %s', self.name, str(e), exc_info=True)
            self._notify_error('Processing Error', 
                _('Could not process the MSG file: %s') % str(e))
            return False

    def _notify_error(self, title, message):
        """Show error notification to the user."""
        self.env['bus.bus']._sendone(self.env.user.partner_id, 'notification', {
            'type': 'danger',
            'title': title,
            'message': message,
            'sticky': True,
        })

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super().create(vals_list)
        for attachment in attachments:
            if attachment._is_msg_file():
                attachment.process_msg_as_email()
        return attachments
