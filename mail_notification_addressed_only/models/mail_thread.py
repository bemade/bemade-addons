from odoo import api, models, modules

TEST_CONTEXT_KEY = "test_mail_notification_addressed_only"


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.model
    def _addressed_only_applies(self):
        """Whether this model is listed. Inert (False) unless it has an
        active rule; abstract models and discuss channels never apply. During
        tests it applies only with the ``test_mail_notification_addressed_only``
        context key."""
        if self._abstract or self._name == "discuss.channel":
            return False
        # While a test suite runs, stay inert unless the test opts in, so the
        # suites of other modules keep their stock notification expectations
        # when this module is installed alongside them.
        if modules.module.current_test and not self.env.context.get(
            TEST_CONTEXT_KEY
        ):
            return False
        return self._name in self.env[
            "mail.addressed.only.rule"
        ]._get_listed_model_names()

    def _addressed_only_partner_ids(self, message, msg_vals):
        msg_vals = msg_vals or {}
        if "partner_ids" in msg_vals:
            addressed = set(msg_vals["partner_ids"] or [])
        else:
            addressed = set(message.sudo().partner_ids.ids)
        # composer Cc/Bcc partners (mail_composer_cc_bcc)
        for key in ("partner_cc_ids", "partner_bcc_ids"):
            extra = self.env.context.get(key)
            if extra:
                addressed.update(extra.ids if hasattr(extra, "ids") else extra)
        return addressed

    def _notify_get_recipients(self, message, msg_vals=False, **kwargs):
        recipients_data = super()._notify_get_recipients(
            message, msg_vals=msg_vals, **kwargs
        )
        if not recipients_data or not self._addressed_only_applies():
            return recipients_data
        addressed = self._addressed_only_partner_ids(message, msg_vals)
        result = []
        for rdata in recipients_data:
            # Only internal users (real, non-shared user), email preference,
            # not addressed. Externals and bare emails have no uid; do not
            # rely on ``type``, other modules rewrite it.
            if (
                rdata.get("notif") == "email"
                and rdata.get("uid")
                and not rdata.get("ushare")
                and rdata.get("id") not in addressed
            ):
                rdata = dict(rdata, notif="inbox")
            result.append(rdata)
        return result
