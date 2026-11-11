# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .zeffy_client import ZeffyClient

_logger = logging.getLogger(__name__)

SYNC_MODELS = ("zeffy.campaign", "zeffy.contact", "zeffy.payment")


class ResCompany(models.Model):
    _inherit = "res.company"

    zeffy_api_key = fields.Char(string="Zeffy API key", groups="base.group_system", copy=False)
    zeffy_last_sync = fields.Datetime(string="Last Zeffy synchronization", readonly=True, copy=False)
    zeffy_last_sync_error = fields.Text(string="Last Zeffy error", readonly=True, copy=False)
    zeffy_contact_watermark = fields.Integer(
        readonly=True,
        copy=False,
        help="Zeffy 'updated' timestamp up to which contacts were read.",
    )

    def _zeffy_sync(self):
        """Synchronize this company from Zeffy. Raises on failure; the caller
        decides what to roll back. Return the number of records created or
        updated, per model."""
        self.ensure_one()
        api_key = self.sudo().zeffy_api_key
        if not api_key:
            raise UserError(_("No Zeffy API key is configured for %s.", self.name))
        client = ZeffyClient(api_key)
        cache = {name: self.env[name]._zeffy_existing(self) for name in SYNC_MODELS}
        stats = {name: self.env[name]._zeffy_sync(client, self, cache) for name in SYNC_MODELS}
        self.write({"zeffy_last_sync": fields.Datetime.now(), "zeffy_last_sync_error": False})
        return stats

    def _zeffy_sync_safe(self):
        """``_zeffy_sync`` with this company's work rolled back on failure.
        Return ``(stats, error_message)``."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                return self._zeffy_sync(), None
        except Exception as exc:  # noqa: BLE001 - one company must not stop the others
            self.env.invalidate_all()
            _logger.warning("Zeffy synchronization failed for %s: %s", self.name, exc, exc_info=True)
            message = str(exc) or exc.__class__.__name__
            self.zeffy_last_sync_error = message
            return None, message

    @api.model
    def _cron_zeffy_sync(self):
        companies = self.sudo().search([("zeffy_api_key", "!=", False)])
        for company in companies:
            company._zeffy_sync_safe()
