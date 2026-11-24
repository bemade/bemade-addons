import logging

from odoo import api, models
from odoo.tools import email_normalize, email_split

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.model
    def message_route(self, message, message_dict, model=None, thread_id=None, custom_values=None):
        parent_id = message_dict.get("parent_id")
        routes = super().message_route(
            message, message_dict, model=model, thread_id=thread_id, custom_values=custom_values
        )
        try:
            return self._mail_send_as_keep_reply(message, message_dict, routes, parent_id) or routes
        except Exception:
            # Never lose an email because of this rule: keep the routes computed so far.
            _logger.exception(
                "Send-as reply routing failed for Message-Id %s, keeping the default routes",
                message_dict.get("message_id"),
            )
            return routes

    @api.model
    def _mail_send_as_keep_reply(self, message, message_dict, routes, parent_id):
        """Keep a reply to a "sent as a team inbox" email on its document.

        A message sent as a team inbox carries that inbox in Reply-To. The
        inbox is usually the alias of another model (a helpdesk team creating
        tickets), which core reads as a forward: the reply would open a new
        record through the alias instead of landing on the document. When the
        email answers such a message and is addressed to the inbox it was sent
        from, route it back to the document instead of the alias route(s).

        :return: the new routes, or None to keep ``routes``.
        """
        if not parent_id:
            return None
        parent = self.env["mail.message"].sudo().browse(parent_id).exists()
        if not parent or not parent.model or not parent.res_id:
            return None
        if any(route[0] == parent.model and route[1] == parent.res_id for route in routes):
            return None
        sent_as = {
            email
            for email in (email_normalize(parent.reply_to or ""), email_normalize(parent.email_from or ""))
            if email
        }
        if not sent_as:
            return None
        recipients = {
            (email_normalize(email) or email).lower()
            for field in (message_dict.get("to"), message_dict.get("cc"), message_dict.get("recipients"))
            for email in email_split(field or "")
        }
        addressed = sent_as & recipients
        if not addressed:
            return None
        aliases = self.env["mail.alias"].sudo().search([("alias_full_name", "in", list(addressed))])
        # Only the aliases core treats as a forward (another model than the
        # document's); a same-model alias already routes the reply.
        aliases = aliases.filtered(lambda a: a.alias_model_id.model != parent.model)
        if not aliases:
            return None
        hidden = [route for route in routes if route[4] and route[4] in aliases]
        if not hidden:
            return None
        user_id = self._mail_find_user_for_gateway(message_dict["email_from"]).id or self.env.uid
        route = self._routing_check_route(
            message,
            message_dict,
            (parent.model, parent.res_id, None, user_id, self.env["mail.alias"]),
            raise_exception=False,
        )
        if not route:
            return None
        message_dict["parent_id"] = parent.id
        _logger.info(
            "Routing mail from %s with Message-Id %s: reply to %s,%s kept on the document "
            "instead of a new record through %s",
            message_dict.get("email_from"), message_dict.get("message_id"),
            parent.model, parent.res_id, ", ".join(aliases.mapped("alias_full_name")),
        )
        return [route] + [r for r in routes if r not in hidden]
