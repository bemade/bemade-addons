import re

from lxml import etree, html
from markupsafe import Markup, escape

from odoo import models
from odoo.tools.mail import is_html_empty

from ..tools import strip_printed_signatures

SIGNATURE_CLASS = "o_bemade_mail_signature"
# Classes of the signature blocks that core's full composer and this module put
# in a body: when one is present the body is already signed.
SIGNED_MARKERS = (SIGNATURE_CLASS, "o-signature-container")


def _html_text(content):
    """Text of an HTML fragment with whitespace collapsed (for comparisons)."""
    if not content:
        return ""
    try:
        text = html.fromstring(f"<div>{content}</div>").text_content()
    except (etree.ParserError, ValueError):
        text = str(content)
    return " ".join(text.split())


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    # ------------------------------------------------------------------
    # Signature block
    # ------------------------------------------------------------------

    def _mail_signature_get_block(self, author):
        """Return the signature block an email from ``author`` on this record
        carries, as it is appended to the message body, or ``""``.

        The signature is taken from ``_notify_by_email_prepare_rendering_context``
        (the hook the notification layout reads), so any module that turns the
        signature off for a flow through that hook turns the block off too.

        :param author: ``res.partner`` record of the message author
        :rtype: Markup | str
        """
        self.ensure_one()
        if not author or self._name == "discuss.channel":
            return ""
        user = author.sudo().main_user_id
        if not user or user.share or is_html_empty(user.signature):
            return ""
        comment_id = self.env["ir.model.data"]._xmlid_to_res_id("mail.mt_comment")
        render_values = self._notify_by_email_prepare_rendering_context(
            self.env["mail.message"],
            msg_vals={
                "author_id": author.id,
                "email_add_signature": True,
                "message_type": "comment",
                "model": self._name,
                "res_id": self.id,
                "subtype_id": comment_id,
                "tracking_value_ids": [],
            },
            force_record_name=self.display_name or " ",
        )
        signature = render_values.get("signature")
        if not render_values.get("email_add_signature") or is_html_empty(signature):
            return ""
        return Markup('<div class="%s" data-o-mail-quote="1">%s</div>') % (
            SIGNATURE_CLASS,
            signature,
        )

    def _mail_signature_template_users(self, author):
        """Users whose signature a template rendered on this record may print:
        the users of the record's stored many2one fields to ``res.users``
        (salesperson, buyer, invoice user, responsible, ...), the current user
        and the author's user."""
        self.ensure_one()
        users = self.env.user | author.sudo().main_user_id
        record = self.sudo()
        for name, field in record._fields.items():
            if field.type == "many2one" and field.comodel_name == "res.users" and field.store:
                users |= record[name]
        return users.sudo()

    def _mail_signature_apply_to_template_body(self, body, author):
        """One signature, the sender's, at the end of a rendered template body.

        Remove every user signature the template printed (see
        ``_mail_signature_template_users``), then append ``author``'s signature
        block. Unchanged when the sender gets no signature on this record (the
        rendering hook turned it off, no signature, ...) or when the body is
        already signed by this module.
        """
        self.ensure_one()
        if is_html_empty(body) or SIGNATURE_CLASS in str(body):
            return body
        block = self._mail_signature_get_block(author)
        if not block:
            return body
        signatures = [
            (user.signature, user.name)
            for user in self._mail_signature_template_users(author)
            if not is_html_empty(user.signature)
        ]
        body = strip_printed_signatures(Markup(body), signatures)
        return Markup(body) + block

    def _mail_signature_in_body(self, body, author):
        """Whether ``body`` already holds ``author``'s signature block."""
        if not body:
            return False
        body = str(body)
        if any(marker in body for marker in SIGNED_MARKERS):
            return True
        user = author.sudo().main_user_id
        signature_text = _html_text(user.signature) if user else ""
        if not signature_text:
            return False
        pattern = r"--\s*" + re.escape(signature_text)
        return bool(re.search(pattern, _html_text(body)))

    # ------------------------------------------------------------------
    # Post
    # ------------------------------------------------------------------

    def _mail_signature_post_applies(self, kwargs):
        """A comment that notifies by email with the author signature, through
        the default layout, written by a logged-in user."""
        if len(self) != 1 or self._name == "discuss.channel":
            return False
        if kwargs.get("message_type", "notification") != "comment":
            return False
        if not kwargs.get("email_add_signature", True):
            return False
        if kwargs.get("email_layout_xmlid"):
            return False
        if self.env.user._is_public():
            return False
        comment_id = self.env["ir.model.data"]._xmlid_to_res_id("mail.mt_comment")
        subtype_id = kwargs.get("subtype_id")
        if kwargs.get("subtype_xmlid"):
            subtype_id = self.env["ir.model.data"]._xmlid_to_res_id(kwargs["subtype_xmlid"])
        return subtype_id == comment_id

    def message_post(self, **kwargs):
        if self._mail_signature_post_applies(kwargs):
            author_id, _email_from = self._message_compute_author(
                kwargs.get("author_id"), kwargs.get("email_from")
            )
            author = self.env["res.partner"].browse(author_id)
            block = self._mail_signature_get_block(author) if author else ""
            if block:
                body = kwargs.get("body") or ""
                if kwargs.get("body_is_html") and self.env.user._is_internal():
                    body = Markup(body)
                body = escape(body)
                if self._mail_signature_in_body(body, author):
                    # Typed or pasted by the user: shown as is, not added again.
                    kwargs["email_add_signature"] = False
                else:
                    # Keep ``email_add_signature`` as given: the block in the
                    # body stands for it, and the rendering hook below stops the
                    # layout from printing a second copy.
                    body = body + block
                kwargs.update(body=body, body_is_html=False)
        return super().message_post(**kwargs)

    def _notify_by_email_prepare_rendering_context(self, message, msg_vals=False, **kwargs):
        """The layout does not print the author signature when the message body
        already carries this module's signature block."""
        render_values = super()._notify_by_email_prepare_rendering_context(
            message, msg_vals=msg_vals, **kwargs
        )
        if render_values.get("email_add_signature"):
            body = (msg_vals or {}).get("body") if msg_vals and "body" in msg_vals else message.body
            if body and SIGNATURE_CLASS in str(body):
                render_values["email_add_signature"] = False
                render_values["signature"] = ""
        return render_values
