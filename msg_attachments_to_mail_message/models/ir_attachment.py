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
        """Convert MSG file to standard email format and process it using Odoo's mail module."""
        self.ensure_one()
        _logger.info('Starting MSG processing for file: %s (model: %s, res_id: %s)', 
                    self.name, self.res_model, self.res_id)

        if not self._is_msg_file():
            _logger.warning('File %s is not a valid MSG file', self.name)
            self._notify_error('Invalid File', 
                _('The selected file is not a valid MSG file'))
            return False
            
        if not self.datas:
            try:
                # Try to reload data from filestore
                self.datas = self.datas
            except Exception as e:
                _logger.error('Failed to read file %s from filestore: %s', self.name, str(e))
                self._notify_error('File Access Error', 
                    _('The MSG file could not be read from the filestore. The file may have been moved or deleted.'))
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
            email_msg['Subject'] = self._clean_header_value(msg_file.subject) or _("No Subject")
            email_msg['From'] = self._clean_header_value(msg_file.sender)
            email_msg['To'] = self._clean_header_value(msg_file.to)
            email_msg['Cc'] = self._clean_header_value(msg_file.cc)
            email_msg['Date'] = msg_file.date.strftime('%a, %d %b %Y %H:%M:%S %z') if msg_file.date else ''
            email_msg['References'] = self._clean_header_value(msg_file.header.get('References', ''))
            email_msg['In-Reply-To'] = self._clean_header_value(msg_file.header.get('In-Reply-To', ''))
            email_msg['Message-ID'] = self._clean_header_value(msg_file.header.get('Message-Id', ''))
            
            # Add X-Headers to force message association
            if self.res_model and self.res_id:
                email_msg['X-Odoo-Objects'] = f'{self.res_model}-{self.res_id}'
            
            # Set the body
            if msg_file.body:
                _logger.info('Processing message body')
                # Convert [cid:xxx] to proper HTML img tags
                body = msg_file.body
                cid_pattern = r'\[cid:([^\]]+)\]'
                body = re.sub(cid_pattern, r'<img src="cid:\1">', body)
                # Nettoyer le HTML si nécessaire
                if '<html' in body.lower():
                    body = html_sanitize(body)
                email_msg.set_content(body, subtype='html')
                _logger.debug('Message body length: %d characters', len(body))
            else:
                _logger.warning('No message body found')
                email_msg.set_content('', subtype='html')
            
            # Add attachments
            attachment_mapping = {}
            attachment_ids = []
            _logger.info('Processing %d attachments', len(msg_file.attachments))
            for idx, attachment in enumerate(msg_file.attachments, 1):
                if not hasattr(attachment, 'data') or not attachment.data:
                    _logger.warning('Attachment %d has no data, skipping', idx)
                    continue
                    
                maintype, subtype = (attachment.mimetype or 'application/octet-stream').split('/', 1)
                headers = {}
                
                filename = None
                if hasattr(attachment, 'filename'):
                    filename = attachment.filename
                elif hasattr(attachment, 'longFilename'):
                    filename = attachment.longFilename
                elif hasattr(attachment, 'shortFilename'):
                    filename = attachment.shortFilename
                
                _logger.info('Processing attachment %d: %s (%s/%s)', 
                            idx, filename or 'unknown.bin', maintype, subtype)
                
                if hasattr(attachment, 'content_id') and attachment.content_id:
                    # Ensure Content-ID is properly formatted with <>
                    cid = attachment.content_id.strip('<>')
                    headers['Content-ID'] = f'<{cid}>'
                    
                # Create Odoo attachment for all attachments, not just those with CID
                try:
                    odoo_attachment = self.env['ir.attachment'].create({
                        'name': filename or 'unknown.bin',
                        'datas': base64.b64encode(attachment.data),
                        'mimetype': attachment.mimetype or 'application/octet-stream',
                        'res_model': self.res_model,
                        'res_id': self.res_id,
                    })
                    _logger.info('Created Odoo attachment: %s (ID: %s)', 
                                odoo_attachment.name, odoo_attachment.id)
                    
                    attachment_ids.append(odoo_attachment.id)
                    if headers.get('Content-ID'):
                        attachment_mapping[cid] = odoo_attachment.id
                except Exception as e:
                    _logger.error('Failed to create attachment %s: %s', filename, str(e))
                
                email_msg.add_attachment(
                    attachment.data,
                    maintype=maintype,
                    subtype=subtype,
                    filename=filename or 'unknown.bin',
                    headers=headers
                )
            
            # Process using Odoo's standard mail handling
            thread_model = self.env[self.res_model] if self.res_model else self.env['mail.thread']
            _logger.info('Using thread model: %s', thread_model._name)
            
            # Forcer le contexte pour la création du message
            context = {
                'default_model': self.res_model,
                'default_res_id': self.res_id,
                'mail_create_nosubscribe': True,
                'mail_create_nolog': True,
                'mail_notify_force_send': False,
                'mail_create_force_model': self.res_model,
                'mail_thread_quote': False,
            }
            _logger.info('Setting context for message creation: %s', context)
            thread_model = thread_model.with_context(**context)
            
            # Créer directement le message si nous avons un modèle et un ID
            if self.res_model and self.res_id:
                _logger.info('Creating message directly for model %s with ID %s', 
                            self.res_model, self.res_id)
                # Trouver l'auteur du message
                author_id = False
                if msg_file.sender:
                    email_normalized = email_normalize(msg_file.sender)
                    _logger.info('Looking for partner with email: %s', email_normalized)
                    partner = self.env['res.partner'].sudo().search([
                        ('email_normalized', '=', email_normalized)
                    ], limit=1)
                    if partner:
                        author_id = partner.id
                        _logger.info('Found partner: %s (ID: %s)', partner.name, partner.id)
                    else:
                        _logger.info('No partner found for email %s', email_normalized)
                
                # Créer le message directement
                try:
                    vals = {
                        'subject': msg_file.subject or _("No Subject"),
                        'body': body if msg_file.body else '',
                        'email_from': msg_file.sender,
                        'author_id': author_id,
                        'message_type': 'email',
                        'model': self.res_model,
                        'res_id': self.res_id,
                        'attachment_ids': [(6, 0, attachment_ids)],
                    }
                    _logger.info('Creating mail.message with values: %s', vals)
                    message = self.env['mail.message'].create(vals)
                    _logger.info('Created message successfully: ID %s', message.id)
                    
                    # Marquer le fichier MSG comme traité
                    self.write({
                        'description': _('Processed as email on %s') % fields.Datetime.now(),
                        'msg_processed': True,
                        'mail_message_id': message.id,
                    })
                    _logger.info('MSG file marked as processed')
                    
                    return message.id
                except Exception as e:
                    _logger.error('Failed to create message: %s', str(e), exc_info=True)
                    raise
            else:
                _logger.info('No model/ID available, falling back to message_process')
                # Si nous n'avons pas de modèle/ID, utiliser message_process
                thread_id = thread_model.message_process(
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
                    # Trouver le message créé
                    message = self.env['mail.message'].search([
                        ('model', '=', self.res_model),
                        ('res_id', '=', thread_id)
                    ], order='id desc', limit=1)
                    
                    if message:
                        _logger.info('Found created message: ID %s', message.id)
                    else:
                        _logger.warning('No message found after processing')
                    
                    # Marquer le fichier MSG comme traité
                    self.write({
                        'description': _('Processed as email on %s') % fields.Datetime.now(),
                        'msg_processed': True,
                        'mail_message_id': message.id if message else False,
                    })
                    _logger.info('MSG file marked as processed')
                else:
                    _logger.error('message_process failed to create thread_id')
                
                return thread_id

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
