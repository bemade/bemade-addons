import requests
import json
from odoo import models, tools
from odoo.exceptions import UserError

class AIService(models.AbstractModel):
    _name = 'ai.service'
    _description = 'AI Service for Open WebUI Integration'

    def _get_headers(self):
        return {
            'Content-Type': 'application/json',
        }

    def _call_openwebui_api(self, endpoint, payload):
        """Appelle l'API Open WebUI avec la configuration de la compagnie actuelle"""
        config = self.env['ai.config'].with_company(self.env.company).get_default_config()
        url = f"{config.openwebui_url}/api/v1/{endpoint}"

        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Erreur de communication avec Open WebUI: {str(e)}")

    def generate_response(self, user_input, conversation_history=None):
        """Génère une réponse en utilisant le modèle Open WebUI de la compagnie"""
        config = self.env['ai.config'].with_company(self.env.company).get_default_config()
        
        messages = []
        if config.system_prompt:
            messages.append({
                "role": "system",
                "content": config.system_prompt
            })

        # Ajouter l'historique de conversation si disponible
        if conversation_history:
            messages.extend(conversation_history)

        # Ajouter l'entrée utilisateur actuelle
        messages.append({
            "role": "user",
            "content": user_input
        })

        payload = {
            "model": config.model_name,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": False
        }

        response = self._call_openwebui_api('chat/completions', payload)
        return response.get('choices', [{}])[0].get('message', {}).get('content', '')
