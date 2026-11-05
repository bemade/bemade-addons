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
# comma-separated ids of the users who get every alert
PARAM_USERS = "bemade_cron_failure_alert.user_ids"
# single user of 19.0.1.0.x/19.0.1.1.0, migrated into PARAM_USERS by 19.0.1.2.0
PARAM_USER_LEGACY = "bemade_cron_failure_alert.user_id"
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

    failure_alert_mode = fields.Selection(
        [
            ("default", "On"),
            ("off", "Off"),
        ],
        string="Failure alert",
        default="default",
        required=True,
        help="On: alert the users and channel set in General Settings, plus "
        "the ones set below (those are alerted even if the option is off in "
        "Settings).\n"
        "Off: never alert for this scheduled action; failures are only logged.",
    )
    failure_alert_user_ids = fields.Many2many(
        "res.users",
        "ir_cron_failure_alert_user_rel",
        "cron_id",
        "user_id",
        string="Also alert",
        domain=[("share", "=", False)],
        help="Users who also receive a To-Do activity when this scheduled "
        "action fails or is switched off, on top of the users set in General "
        "Settings.",
    )
    failure_alert_channel_id = fields.Many2one(
        "discuss.channel",
        string="Also post in channel",
        domain=[("channel_type", "=", "channel")],
        help="Discuss channel where this scheduled action's failure alerts "
        "are also posted, on top of the channel set in General Settings.",
    )

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
        targets = self._cron_failure_alert_targets(job, deactivated)
        if targets is None:
            return
        users, channels = targets
        _logger.warning(
            "Scheduled action %r (%s) %s.",
            job["cron_name"],
            job["id"],
            "was switched off after repeated failures" if deactivated else "failed",
        )
        if not users and not channels:
            _logger.warning(
                "Scheduled action failure alerts are on, but no user or channel "
                "is set: nothing to notify for %r (%s).",
                job["cron_name"],
                job["id"],
            )
            return

        summary, body = self._cron_failure_alert_bilingual(job, error, deactivated)
        for user in users:
            self._cron_failure_alert_todo(job, user, summary, body)
        for channel in channels:
            channel.message_post(
                body=body,
                author_id=self.env.ref("base.partner_root").id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

    @api.model
    def _cron_failure_alert_targets(self, job, deactivated):
        """Return ``(users, channels)`` to alert for ``job``, or ``None``.

        The recipients are the scheduled action's own "Also alert" users and
        channel, plus -- when the Settings option is on -- the Settings users
        and channel. Both are recordsets, so a user or a channel set in both
        places appears once. ``None`` means nothing to alert and nothing to
        say about it: mode "Off" (logged here), or the Settings option off
        with no extra recipient on the scheduled action.
        """
        cron = self.browse(job["id"]).exists()
        mode = cron.failure_alert_mode or "default"
        if mode == "off":
            _logger.warning(
                "Scheduled action %r (%s) %s; its failure alert is off.",
                job["cron_name"],
                job["id"],
                "was switched off after repeated failures"
                if deactivated
                else "failed",
            )
            return None
        users = cron.failure_alert_user_ids.filtered("active")
        channels = cron.failure_alert_channel_id.exists()
        icp = self.env["ir.config_parameter"].sudo()
        if str2bool(icp.get_param(PARAM_ENABLED) or "False", False):
            users |= self._cron_failure_alert_settings_users()
            channels |= self._cron_failure_alert_record(
                "discuss.channel", icp.get_param(PARAM_CHANNEL)
            )
        elif not users and not channels:
            return None
        return users, channels

    @api.model
    def _cron_failure_alert_settings_users(self):
        """Active users set in General Settings to receive every alert."""
        value = self.env["ir.config_parameter"].sudo().get_param(PARAM_USERS) or ""
        ids = []
        for part in value.split(","):
            try:
                ids.append(int(part))
            except ValueError:
                continue
        return self.env["res.users"].browse(ids).exists().filtered("active")

    @api.model
    def _cron_failure_alert_link(self, cron_id):
        return "/odoo/action-base.ir_cron_act/%s" % cron_id

    @api.model
    def _cron_failure_alert_todo(self, job, user, summary, body):
        """Create the alert To-Do, or add the alert to the one still open.

        A scheduled action has at most one open alert To-Do per user: a new
        alert (new failure streak, switch-off) goes on top of its note.
        """
        todo_type = self.env.ref("mail.mail_activity_data_todo")
        today = fields.Date.context_today(self.with_user(user))
        # free-standing To-Do (ir.cron is not a mail.thread): found by the
        # link to the scheduled action that every alert note carries
        open_todo = self.env["mail.activity"].search(
            [
                ("res_model", "=", False),
                ("activity_type_id", "=", todo_type.id),
                ("user_id", "=", user.id),
                ("note", "ilike", '%s"' % self._cron_failure_alert_link(job["id"])),
            ],
            order="id desc",
            limit=1,
        )
        if open_todo:
            open_todo.write(
                {
                    "summary": summary,
                    "note": body + Markup("<hr/>") + (open_todo.note or ""),
                    "date_deadline": today,
                }
            )
            return open_todo
        return self.env["mail.activity"].create(
            {
                "activity_type_id": todo_type.id,
                "summary": summary,
                "note": body,
                "user_id": user.id,
                "date_deadline": today,
            }
        )

    @api.model
    def _cron_failure_alert_record(self, model, value):
        try:
            record_id = int(value or 0)
        except (TypeError, ValueError):
            return self.env[model]
        return self.env[model].browse(record_id).exists()

    @api.model
    def _cron_failure_alert_langs(self):
        """Languages the alerts are written in: French, then English.

        Alerts are read later by other people than their recipient, so they
        never follow a user's language. Only installed languages are used
        (rendering in an inactive one fails); without French, the alert is
        written in the environment's language alone.
        """
        installed = {code for code, _name in self.env["res.lang"].get_installed()}
        if "fr_FR" not in installed:
            return [self.env.lang or "en_US"]
        return [lang for lang in ("fr_FR", "en_US") if lang in installed]

    @api.model
    def _cron_failure_alert_bilingual(self, job, error, deactivated):
        """Return ``(summary, html_body)``: French first, then English.

        The summary is "<French> / <English>"; the body is one block per
        language, each starting with its summary in bold.
        """
        summaries = []
        body = Markup()
        for lang in self._cron_failure_alert_langs():
            summary, block = self.with_context(
                lang=lang
            )._cron_failure_alert_content(job, error, deactivated)
            summaries.append(summary)
            body += Markup("<p><b>%s</b></p>") % summary + block
        return " / ".join(summaries), body

    @api.model
    def _cron_failure_alert_content(self, job, error, deactivated):
        """Return ``(summary, html_body)`` in the context language only."""
        _ = self.env._
        name = job["cron_name"]
        now = fields.Datetime.to_string(self.env.cr.now().replace(microsecond=0))
        values = {
            "link": Markup('<a href="%s">%s</a>')
            % (self._cron_failure_alert_link(job["id"]), name),
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
