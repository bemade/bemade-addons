from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AIAssistantChannel(models.Model):
    _name = 'ai.assistant.channel'
    _description = 'AI Assistant Channel'
    _inherit = ['mail.thread']

    name = fields.Char(default="Assistant AI", readonly=True, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    active = fields.Boolean(default=True, tracking=True)
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )
    message_ids = fields.One2many(
        'mail.message',
        'res_id',
        string='Messages',
        domain=lambda self: [('model', '=', self._name)],
        tracking=True
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            # Create a dedicated discussion channel for the assistant
            channel = self.env['mail.channel'].create({
                'name': _('Assistant AI - %s', record.company_id.name),
                'channel_type': 'chat',
                'channel_partner_ids': [(4, record.user_id.partner_id.id)],
            })
        return records

    def _get_conversation_history(self, limit=10):
        """Get recent conversation history"""
        self.ensure_one()
        messages = self.env['mail.message'].search([
            ('model', '=', self._name),
            ('res_id', '=', self.id)
        ], limit=limit, order='id desc')
        
        history = []
        for msg in reversed(messages):
            role = "assistant" if msg.author_id == self.user_id.partner_id else "user"
            history.append({
                "role": role,
                "content": msg.body
            })
        return history

    def process_voice_message(self, voice_input):
        """Process voice input and respond"""
        self.ensure_one()
        if not voice_input:
            raise UserError(_('No voice input provided'))
        
        # Get conversation history
        conversation_history = self._get_conversation_history()
        
        # Use AI service to generate response
        ai_service = self.env['ai.service'].with_company(self.company_id)
        response = ai_service.generate_response(voice_input, conversation_history)
        
        # Post response as message
        self.message_post(
            body=response,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True

    @api.model
    def get_assistant_for_user(self, user_id=None):
        """Get or create an assistant for the user in their company"""
        if not user_id:
            user_id = self.env.user.id
            
        assistant = self.search([
            ('user_id', '=', user_id),
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)
        
        if not assistant:
            assistant = self.create({
                'user_id': user_id,
                'company_id': self.env.company.id
            })
            
        return assistant
