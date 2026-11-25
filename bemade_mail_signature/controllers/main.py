from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request


class MailSignatureController(http.Controller):
    @http.route(
        "/bemade_mail_signature/block", methods=["POST"], type="jsonrpc", auth="user"
    )
    def mail_signature_block(self, thread_model, thread_id):
        """The signature block a comment by the current user on this thread gets
        appended (same HTML as ``message_post``), or ``""``."""
        if not thread_id or thread_model not in request.env:
            return ""
        Model = request.env[thread_model]
        if not isinstance(Model, request.env.registry["mail.thread"]):
            return ""
        record = Model.browse(int(thread_id))
        try:
            record.check_access("read")
            if not record.exists():
                return ""
        except (AccessError, MissingError):
            return ""
        return str(record._mail_signature_get_block(request.env.user.partner_id))
