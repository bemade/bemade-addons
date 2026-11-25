# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import _, fields, models

from .zeffy_client import ZeffyAuthError, ZeffyClient, ZeffyError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    zeffy_api_key = fields.Char(
        related="company_id.zeffy_api_key",
        readonly=False,
        groups="base.group_system",
    )
    zeffy_last_sync = fields.Datetime(related="company_id.zeffy_last_sync")
    zeffy_last_sync_error = fields.Text(related="company_id.zeffy_last_sync_error")

    def _zeffy_notification(self, message, kind):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Zeffy"),
                "message": message,
                "type": kind,
                "sticky": kind == "danger",
            },
        }

    def action_zeffy_test_connection(self):
        """Check the key as typed. Deliberately a button, never run on save."""
        self.ensure_one()
        if not self.zeffy_api_key:
            return self._zeffy_notification(_("Enter a Zeffy API key first."), "warning")
        try:
            ZeffyClient(self.zeffy_api_key).test_connection()
        except ZeffyAuthError:
            return self._zeffy_notification(
                _("Zeffy rejected this API key. Generate a new one in Zeffy, Settings > Integrations."),
                "danger",
            )
        except ZeffyError as exc:
            return self._zeffy_notification(_("Zeffy error: %s", exc), "danger")
        return self._zeffy_notification(_("Connection to Zeffy succeeded."), "success")

    def action_zeffy_sync_now(self):
        self.ensure_one()
        stats, error = self.company_id._zeffy_sync_safe()
        if error:
            return self._zeffy_notification(_("Zeffy synchronization failed: %s", error), "danger")
        return self._zeffy_notification(
            _(
                "Zeffy synchronization done. Created or updated: %(campaigns)s campaign(s), "
                "%(contacts)s contact(s), %(payments)s payment(s).",
                campaigns=stats["zeffy.campaign"],
                contacts=stats["zeffy.contact"],
                payments=stats["zeffy.payment"],
            ),
            "success",
        )
