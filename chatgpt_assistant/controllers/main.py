
from odoo import http
from odoo.http import request
import openai
import pandas as pd

class DiscussChatGPT(http.Controller):
    @http.route('/discuss/chatgpt', type='json', auth='user')
    def chatgpt_respond(self, message, attachment_id=None):
        openai.api_key = request.env['ir.config_parameter'].sudo().get_param('chatgpt.api_key')

        if attachment_id:
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if attachment.mimetype == 'text/csv':
                data = pd.read_csv(attachment._full_path(attachment.store_fname))
                processed_data = data.describe().to_string()
                return {'response': f"Analyse des données : \n{processed_data}"}

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": message}]
        )
        return {'response': response['choices'][0]['message']['content']}
