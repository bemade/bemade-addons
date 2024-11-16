from odoo import models, fields, api, _
from odoo.exceptions import UserError
import openai
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    api_key = fields.Char(
        string="API Key",
        config_parameter='openai_connector.api_key',
        help="API Key for OpenAI, used as a default if the company-specific key is not set. Format should start with 'sk-'"
    )
    organization = fields.Char(
        string="Organization ID",
        config_parameter='openai_connector.organization',
        help="Organization ID for OpenAI, used as a default if the company-specific ID is not set. Format should start with 'org-'"
    )

    connection_status = fields.Char(
        string="Connection Status",
        compute='_compute_connection_status',
        help="Displays the current connection status with OpenAI."
    )

    @api.depends('api_key', 'organization')
    def _compute_connection_status(self):
        for record in self:
            try:
                if record.api_key and record.organization:  # Vérifie que les champs ne sont pas vides
                    record._test_openai_connection()
                    record.connection_status = "Connected"
                else:
                    record.connection_status = "Disconnected"
            except Exception as e:
                record.connection_status = "Disconnected"
                _logger.error(f"OpenAI connection test failed: {str(e)}")

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'openai_connector.api_key', self.api_key)
        self.env['ir.config_parameter'].sudo().set_param(
            'openai_connector.organization', self.organization)

        # Test de connexion automatique lors de l'enregistrement si les champs sont remplis
        if self.api_key and self.organization:
            self._test_openai_connection()

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(
            api_key=self.env['ir.config_parameter'].sudo().get_param(
                'openai_connector.api_key', default=''),
            organization=self.env['ir.config_parameter'].sudo().get_param(
                'openai_connector.organization', default='')
        )
        return res

    def _test_openai_connection(self):
        """Method to test connection to OpenAI."""
        if not self.api_key or not self.organization:
            return  # Ne fait rien si l'un des champs est vide

        try:
            client = openai.OpenAI(organization=self.organization, api_key=self.api_key)
            client.models.list()  # Test basique de la connexion
        except Exception as e:
            raise UserError(_("Failed to connect to OpenAI API. Please check the API Key and Organization ID.\nError: %s") % str(e))

    def action_test_openai_connection(self):
        """Action to test connection manually and display the result."""
        try:
            self._test_openai_connection()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Connection Test Successful"),
                    'message': _("The connection to OpenAI was successful."),
                    'sticky': False,
                },
            }
        except UserError as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Connection Test Failed"),
                    'message': str(e),
                    'sticky': True,
                },
            }