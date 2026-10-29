import logging
import traceback

from markupsafe import Markup, escape

from odoo import SUPERUSER_ID, api, fields, models
from odoo.tools import str2bool

from odoo.addons.base.models.ir_cron import (
    MIN_FAILURE_COUNT_BEFORE_DEACTIVATION,
    CompletionStatus,
)

_logger = logging.getLogger(__name__)

PARAM_ENABLED = "bemade_cron_failure_alert.enabled"
PARAM_USER = "bemade_cron_failure_alert.user_id"
PARAM_CHANNEL = "bemade_cron_failure_alert.channel_id"

# Keep the end of the traceback: the exception itself is at the bottom.
ERROR_MAX_CHARS = 3000

# Error text of the last failed run, keyed by (database, cron id).
#
# The exception is only known inside ``_callback``, which runs on the job's own
# cursor; the failure bookkeeping (``_update_failure_count``) runs afterwards on
# the cron worker's cursor. Both happen in the same worker thread, one job at a
# time, and a job row is locked while it runs, so a plain dict keyed by job is
# enough to hand the text over. ``_update_failure_count`` always pops the entry.
_LAST_ERRORS = {}


class IrCron(models.Model):
    _inherit = "ir.cron"

    def _callback(self, cron_name, server_action_id):
        try:
            return super()._callback(cron_name, server_action_id)
        except Exception:
            _LAST_ERRORS[(self.env.cr.dbname, self.id)] = traceback.format_exc()[
                -ERROR_MAX_CHARS:
            ]
            raise

    @api.model
    def _update_failure_count(self, job, status):
        error = _LAST_ERRORS.pop((self.env.cr.dbname, job["id"]), None)
        super()._update_failure_count(job, status)
        if status != CompletionStatus.FAILED:
            return
        deactivated = False
        if job["active"]:
            self.env.cr.execute("SELECT active FROM ir_cron WHERE id = %s", [job["id"]])
            row = self.env.cr.fetchone()
            deactivated = bool(row) and not row[0]
        first_failure = not job["failure_count"]
        if first_failure or deactivated:
            self._cron_failure_alert(job, error, deactivated)

    @api.model
    def _cron_failure_alert(self, job, error, deactivated):
        """Raise the alert in its own transaction; never let it escape.

        The caller's cursor carries the cron's own bookkeeping (failure
        counter, deactivation, next call). An alert that fails half-way must
        not leave anything pending on it, so the alert gets a cursor of its
        own, and any error is logged and swallowed.
        """
        try:
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env["ir.cron"]._cron_failure_alert_send(job, error, deactivated)
        except Exception:
            _logger.exception(
                "Could not raise the failure alert for scheduled action %r (%s)",
                job["cron_name"],
                job["id"],
            )

    @api.model
    def _cron_failure_alert_send(self, job, error, deactivated):
        icp = self.env["ir.config_parameter"].sudo()
        if not str2bool(icp.get_param(PARAM_ENABLED) or "False", False):
            return
        user = self._cron_failure_alert_record("res.users", icp.get_param(PARAM_USER))
        channel = self._cron_failure_alert_record(
            "discuss.channel", icp.get_param(PARAM_CHANNEL)
        )
        _logger.warning(
            "Scheduled action %r (%s) %s.",
            job["cron_name"],
            job["id"],
            "was switched off after repeated failures" if deactivated else "failed",
        )
        if not user and not channel:
            _logger.warning(
                "Scheduled action failure alerts are on, but no user or channel "
                "is set: nothing to notify for %r (%s).",
                job["cron_name"],
                job["id"],
            )
            return

        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        lang = user.lang or (admin and admin.lang) or "en_US"
        cron = self.with_context(lang=lang)
        summary, body = cron._cron_failure_alert_content(job, error, deactivated)

        if user:
            cron.env["mail.activity"].create(
                {
                    "activity_type_id": cron.env.ref("mail.mail_activity_data_todo").id,
                    "summary": summary,
                    "note": body,
                    "user_id": user.id,
                    "date_deadline": fields.Date.context_today(cron.with_user(user)),
                }
            )
        if channel:
            channel.message_post(
                body=Markup("<p><b>%s</b></p>") % summary + body,
                author_id=cron.env.ref("base.partner_root").id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

    @api.model
    def _cron_failure_alert_record(self, model, value):
        try:
            record_id = int(value or 0)
        except (TypeError, ValueError):
            return self.env[model]
        return self.env[model].browse(record_id).exists()

    @api.model
    def _cron_failure_alert_content(self, job, error, deactivated):
        """Return ``(summary, html_body)`` in the context language."""
        _ = self.env._
        name = job["cron_name"]
        now = fields.Datetime.to_string(self.env.cr.now().replace(microsecond=0))
        values = {
            "link": Markup('<a href="/odoo/action-base.ir_cron_act/%s">%s</a>')
            % (job["id"], name),
            "count": MIN_FAILURE_COUNT_BEFORE_DEACTIVATION,
            "time": now,
        }
        if deactivated:
            summary = _("Scheduled action switched off: %(name)s", name=name)
            intro = _(
                "Odoo switched off the scheduled action %(link)s after it failed "
                "%(count)s times in a row over more than a week (last failure: "
                "%(time)s UTC). It will not run again until it is re-enabled."
            )
        else:
            summary = _("Scheduled action failed: %(name)s", name=name)
            intro = _(
                "The scheduled action %(link)s failed at %(time)s UTC. Odoo will "
                "retry it at its next scheduled time; no other alert will be sent "
                "until it succeeds again, unless Odoo switches it off."
            )
        # Translated templates are plain text: escape them, then let Markup
        # escape the values too -- except the link, which is already Markup.
        body = Markup("<p>%s</p>") % (Markup(escape(intro)) % values)
        if error:
            body += Markup("<pre>%s</pre>") % error
        else:
            no_error = _(
                "No error text was captured (for example, the run timed out). "
                "See the server log around %(time)s UTC."
            )
            body += Markup("<p>%s</p>") % (Markup(escape(no_error)) % values)
        return summary, body
