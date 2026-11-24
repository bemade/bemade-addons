from markupsafe import Markup

from odoo import models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _notify_by_email_prepare_rendering_context(
        self,
        message,
        msg_vals=False,
        model_description=False,
        force_email_company=False,
        force_email_lang=False,
        force_record_name=False,
    ):
        """Notification layout: the author's signature shows the signature
        email address (chatter "Send message", replies, message_post)."""
        render_context = super()._notify_by_email_prepare_rendering_context(
            message,
            msg_vals=msg_vals,
            model_description=model_description,
            force_email_company=force_email_company,
            force_email_lang=force_email_lang,
            force_record_name=force_record_name,
        )
        author_user = render_context.get("author_user")
        if render_context.get("email_add_signature") and render_context.get("signature") and author_user:
            record = self[:1] if len(self) == 1 else None
            outgoing = author_user._mail_outgoing_signature(record)
            if outgoing != author_user.sudo().signature:
                render_context["signature"] = Markup("<div>-- <br/>%s</div>") % outgoing
        return render_context

    def _message_create(self, values_list):
        """Message bodies: the signature the web client inserts (full
        composer) or a copy of the stored signature shows the signature email
        address. Only the signature fragment changes; incoming emails are
        never touched."""
        Users = self.env["res.users"].sudo()
        record = self if len(self) == 1 else None
        for values in values_list:
            body = values.get("body")
            if not body or "@" not in body or values.get("message_type") == "email":
                continue
            author = self.env["res.partner"].browse(values["author_id"]) if values.get("author_id") else self.env.user.partner_id
            user = author.main_user_id.sudo()
            if not user or user.share or not user._mail_signature_email(record):
                continue
            body = Users._mail_signature_rewrite_html(body, user, record)
            values["body"] = Users._mail_signature_rewrite_blocks(body, user, record)
        return super()._message_create(values_list)
