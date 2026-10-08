from odoo import api, models
from odoo.tools import str2bool

ICP_ALL_MODELS = "mail_notification_scope.all_models"


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    _NOTIFICATION_SCOPE_NEVER = frozenset({"discuss.channel"})

    # ------------------------------------------------------------
    # Gate
    # ------------------------------------------------------------

    @api.model
    def _notification_scope_applies(self):
        """Whether this model is opted into scoped notifications.

        Inert (False) unless the model has an active rule or the "all
        models" flag is set. Abstract models and discuss channels are
        never scoped.
        """
        if self._abstract or self._name in self._NOTIFICATION_SCOPE_NEVER:
            return False
        if str2bool(
            self.env["ir.config_parameter"].sudo().get_param(ICP_ALL_MODELS), False
        ):
            return True
        return self._name in self.env["mail.notification.scope"]._get_scoped_model_names()

    def _notification_scope_filter_recipients(self, recipients_data):
        """Keep internal users only, and turn their email notifications
        into in-app (inbox) ones.

        Does not rely on ``type``: other modules rewrite it.
        """
        kept = []
        for rdata in recipients_data:
            if not (rdata.get("active") and rdata.get("id") and rdata.get("uid")):
                continue
            if rdata.get("ushare"):
                continue
            if rdata.get("notif") == "email":
                rdata = dict(rdata, notif="inbox")
            kept.append(rdata)
        return kept

    # ------------------------------------------------------------
    # Notification pipeline
    # ------------------------------------------------------------

    def _notify_get_recipients(self, message, msg_vals=False, **kwargs):
        recipients_data = super()._notify_get_recipients(
            message, msg_vals=msg_vals, **kwargs
        )
        if not self._notification_scope_applies():
            return recipients_data
        return self._notification_scope_filter_recipients(recipients_data)

    def _notify_thread_by_email(self, message, recipients_data, **kwargs):
        # Belt and braces: other modules may append recipients after our
        # filter, or call this directly.
        if self._notification_scope_applies():
            recipients_data = self._notification_scope_filter_recipients(
                recipients_data
            )
            self = self.with_context(skip_adding_cc_bcc=True)
        return super(MailThread, self)._notify_thread_by_email(
            message, recipients_data, **kwargs
        )

    def _notify_thread_with_out_of_office(
        self, message, recipients_data, msg_vals=False, **kwargs
    ):
        # An out-of-office auto-reply is an email to the (external) author.
        if self._notification_scope_applies():
            return self.env["mail.message"]
        return super()._notify_thread_with_out_of_office(
            message, recipients_data, msg_vals=msg_vals, **kwargs
        )
