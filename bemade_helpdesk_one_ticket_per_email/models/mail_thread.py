from odoo import models, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.model
    def _message_route_process(self, message, message_dict, routes):
        """
        Process the routes for an incoming message, ensuring only one helpdesk route is used if multiple
        helpdesk routes are detected.

        This override filters the routes to avoid processing a message multiple times for helpdesk models
        (`helpdesk.ticket` and `helpdesk.team`). If multiple helpdesk routes are found, only the first one
        is retained, and a log entry is created to indicate the adjustment.

        Parameters:
            message (object): The incoming message object.
            message_dict (dict): Dictionary of parsed message values.
            routes (list): List of route tuples, each containing the target model and relevant information.

        Returns:
            bool: Result of the `_message_route_process` from the superclass.
        """
        try:
            # Filter routes to keep only those related to helpdesk models if they are present
            helpdesk_routes = [
                r for r in routes if r[0] in ("helpdesk.ticket", "helpdesk.team")
            ]

            if helpdesk_routes:
                _logger.info(
                    "Messages contained helpdesk routes. Only the first one will be used."
                )
                # Retain only the first helpdesk route
                routes = [helpdesk_routes[0]]

            # Call the parent method with potentially modified routes
            return super()._message_route_process(message, message_dict, routes)

        except Exception as e:
            # Log the exception and raise it to ensure errors are traceable
            _logger.error(f"An error occurred in _message_route_process: {str(e)}")
            raise UserError(
                "An unexpected error occurred while processing message routes. Please contact support."
            )
