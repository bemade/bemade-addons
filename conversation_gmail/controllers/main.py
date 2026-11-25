import logging

from werkzeug.exceptions import Forbidden

from odoo.http import request

from odoo.addons.google_gmail.controllers.main import GoogleGmailController

_logger = logging.getLogger(__name__)


class ConversationGmailController(GoogleGmailController):
    """Scopes two behaviours of core's Google callback to
    ``conversation.transport`` only: who may complete the flow, and where
    the browser lands afterwards. ``ir.mail_server`` and
    ``fetchmail.server`` keep core's behaviour untouched."""

    def _get_gmail_record(self, model_name, rec_id, csrf_token):
        record = super()._get_gmail_record(model_name, rec_id, csrf_token)
        if record._name == "conversation.transport" and not request.env.is_admin():
            # The state is already bound to the acting user by the token
            # check; this also refuses a shared transport and a personal one
            # that belongs to somebody else, whatever the state says, so
            # tokens are only ever written to a transport the user owns.
            if not record.user_id or record.user_id.id != request.env.uid:
                _logger.warning(
                    "Google Gmail: user %s may not connect conversation.transport #%s",
                    request.env.uid,
                    record.id,
                )
                raise Forbidden()
        return record

    def _get_redirect_url(self, record):
        if record._name == "conversation.transport":
            # Back to the mailbox that was just connected, not to the user's
            # preferences.
            action = request.env.ref(
                "conversation_inbox.conversation_transport_action_my",
                raise_if_not_found=False,
            )
            if action:
                return f"/odoo/action-{action.id}/{record.id}"
            return f"/odoo/conversation.transport/{record.id}"
        return super()._get_redirect_url(record)
