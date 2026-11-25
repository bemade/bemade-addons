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
        is retained, and a log entry is created to indicate the adjustment. Routes to other models (a
        reply to another document, an alias of another model) are kept, in their original order.

        Parameters:
            message (object): The incoming message object.
            message_dict (dict): Dictionary of parsed message values.
            routes (list): List of route tuples, each containing the target model and relevant information.

        Returns:
            bool: Result of the `_message_route_process` from the superclass.
        """
        try:
            # Helpdesk routes: only the first one is processed
            helpdesk_routes = [
                r for r in routes if r[0] in ("helpdesk.ticket", "helpdesk.team")
            ]

            if len(helpdesk_routes) > 1:
                _logger.info(
                    "Messages contained several helpdesk routes. Only the first one will be used."
                )
                # Retain the first helpdesk route and every non-helpdesk route
                dropped = helpdesk_routes[1:]
                routes = [r for r in routes if not any(r is d for d in dropped)]

            # Call the parent method with potentially modified routes
            return super()._message_route_process(message, message_dict, routes)

        except Exception as e:
            # Log the exception and raise it to ensure errors are traceable
            _logger.error(f"An error occurred in _message_route_process: {str(e)}")
            raise UserError(
                "An unexpected error occurred while processing message routes. Please contact support."
            )
