import logging

from markupsafe import Markup

from odoo import api, models
from odoo.tools import email_normalize, email_split

_logger = logging.getLogger(__name__)

# Key of the thread data the chatter asks for to preview the signature.
SIGNATURE_REQUEST = "mail_company_signature"
# message_dict keys passed from message_route to _message_route_process.
KEPT_REPLY_KEY = "mail_company_signature_kept_reply"
ALIAS_REPLY_KEY = "mail_company_signature_alias_reply"


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    # ------------------------------------------------------------------
    # Sending address
    # ------------------------------------------------------------------
    def _mail_sender_override(self, user):
        """The address ``user`` sends from on this record, imposed by the
        record whoever writes (bridges override it: a helpdesk ticket returns
        its team's inbox).

        :return: dict ``email`` and ``label`` (team name), or None.
        """
        return None

    # ------------------------------------------------------------------
    # Signature
    # ------------------------------------------------------------------
    def _notify_by_email_prepare_rendering_context(
        self,
        message,
        msg_vals=False,
        model_description=False,
        force_email_company=False,
        force_email_lang=False,
        force_record_name=False,
    ):
        """Notification layout: the author's signature is the one built for
        this record (chatter "Send message", replies, message_post)."""
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
            signature = author_user._mail_signature_for(record)
            if signature != author_user.sudo().signature:
                render_context["signature"] = Markup("<div>-- <br/>%s</div>") % signature
        return render_context

    def _thread_to_store(self, store, fields, *, request_list=None):
        """Chatter data: the current user's signature for this record, so
        the composer previews (and the full composer inserts) the signature
        that goes out."""
        super()._thread_to_store(store, fields, request_list=request_list)
        if not request_list or SIGNATURE_REQUEST not in request_list:
            return
        user = self.env.user
        if user._is_public():
            return
        for thread in self:
            store.add(
                thread,
                {"mailCompanySignature": Markup(user._mail_signature_for(thread) or "")},
                as_thread=True,
            )

    # ------------------------------------------------------------------
    # Incoming: a reply stays on its record
    # ------------------------------------------------------------------
    @api.model
    def message_route(self, message, message_dict, model=None, thread_id=None, custom_values=None):
        parent_id = message_dict.get("parent_id")
        routes = super().message_route(
            message, message_dict, model=model, thread_id=thread_id, custom_values=custom_values
        )
        message_dict.pop(KEPT_REPLY_KEY, None)
        message_dict.pop(ALIAS_REPLY_KEY, None)
        try:
            kept = self._mail_keep_record_reply(message, message_dict, routes, parent_id)
            if kept:
                routes = kept
            self._mail_mark_alias_reply(message, message_dict, routes)
        except Exception:
            # Never lose an email because of this rule: keep the routes so far.
            _logger.exception(
                "Reply routing failed for Message-Id %s, keeping the default routes",
                message_dict.get("message_id"),
            )
        return routes

    @api.model
    def _mail_reply_recipients(self, message, message_dict):
        """Normalized To / Cc / Delivered-To addresses of an incoming email."""
        delivered_to = message.get("Delivered-To") if message is not None else ""
        return {
            (email_normalize(email) or email).lower()
            for field in (message_dict.get("to"), message_dict.get("cc"), delivered_to)
            for email in email_split(field or "")
        }

    @api.model
    def _mail_keep_record_reply(self, message, message_dict, routes, parent_id):
        """Keep a reply on the record it answers.

        Core reads a reply addressed to an alias of another model (a helpdesk
        inbox that creates tickets) as a forward: it drops the reply route and
        creates a new record through the alias. When every route core kept is
        such a creation and the email answers a message of a record, route it
        back to that record instead. Active only for the records of companies
        with "Send from the signature address" (their emails carry a team
        inbox in Reply-To); there is no per-model exception.

        :return: ``[route]`` or an empty list to keep ``routes``.
        """
        if not routes or not parent_id:
            return []
        parent = self.env["mail.message"].sudo().browse(parent_id).exists()
        if not parent or not parent.model or not parent.res_id or parent.model not in self.env:
            return []
        if any(route[1] or not route[4] or route[0] == parent.model for route in routes):
            return []
        record = self.env[parent.model].sudo().browse(parent.res_id).exists()
        if not record or not self._mail_reply_keep_applies(record):
            return []
        user_id = self._mail_find_user_for_gateway(message_dict["email_from"]).id or self.env.uid
        route = self._routing_check_route(
            message,
            message_dict,
            (parent.model, parent.res_id, None, user_id, self.env["mail.alias"]),
            raise_exception=False,
        )
        if not route:
            return []
        message_dict["parent_id"] = parent.id
        message_dict[KEPT_REPLY_KEY] = True
        _logger.info(
            "Routing mail from %s with Message-Id %s: reply to %s,%s kept on the record "
            "instead of a new record through %s",
            message_dict.get("email_from"), message_dict.get("message_id"),
            parent.model, parent.res_id, ", ".join(r[4].display_name for r in routes if r[4]),
        )
        return [route]

    @api.model
    def _mail_reply_keep_applies(self, record):
        company = record.company_id if "company_id" in record._fields else self.env["res.company"]
        company = company[:1] or self.env.company
        return bool(company.sudo().mail_send_from_signature_address)

    @api.model
    def _mail_mark_alias_reply(self, message, message_dict, routes):
        """Remember a reply that lands on a record while inboxes of other
        models were among its recipients (kept by the rule above, or routed
        by core with the inbox in Cc), for ``_mail_on_alias_reply``."""
        if len(routes) != 1 or not message_dict.get("parent_id"):
            return
        model, thread_id = routes[0][0], routes[0][1]
        if not model or not thread_id:
            return
        emails = self._mail_reply_recipients(message, message_dict)
        if not emails:
            return
        aliases = self.env["mail.alias"].sudo().search(
            [("alias_full_name", "in", list(emails)), ("alias_model_id.model", "!=", model)]
        )
        if aliases:
            message_dict[ALIAS_REPLY_KEY] = (model, thread_id, aliases.ids)

    @api.model
    def _message_route_process(self, message, message_dict, routes):
        message_dict.pop(KEPT_REPLY_KEY, None)
        alias_reply = message_dict.pop(ALIAS_REPLY_KEY, None)
        result = super()._message_route_process(message, message_dict, routes)
        if alias_reply:
            model, thread_id, alias_ids = alias_reply
            record = self.env[model].sudo().browse(thread_id).exists()
            aliases = self.env["mail.alias"].sudo().browse(alias_ids).exists()
            if record and aliases:
                try:
                    with self.env.cr.savepoint():
                        record._mail_on_alias_reply(aliases, message_dict)
                except Exception:
                    # The reply is already on the record: never undo that.
                    _logger.exception(
                        "Could not handle the reply %s kept on %s,%s",
                        message_dict.get("message_id"), model, thread_id,
                    )
        return result

    def _mail_on_alias_reply(self, aliases, message_dict):
        """Hook: a reply landed on this record while ``aliases`` (inboxes of
        other models, e.g. a helpdesk team's) were among its recipients.
        Called after the reply is posted. Default: nothing."""
        return None
