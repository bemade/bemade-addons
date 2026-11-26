# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5546 (pwa 1.2): phone notifications (Web Push) from the installed
app, on Odoo's own pipeline: its VAPID keys (``mail.push.device
.get_web_push_vapid_public_key``, the ONLY place keys are ever created),
its ``mail.push.device`` rows, its encryption and its cron queue.

* ``portal.kit._pk_push_available()``: True while the kit's switch is on.
* ``portal.kit._pk_push_owner(user)``: an opaque, per-database tag of the
  user's partner, kept by the page next to the subscription it registered
  (a phone shared in a family never re-registers silently for someone
  else).
* ``portal.kit._pk_push_register(...)`` / ``_pk_push_unregister(...)``: the
  routes' rules (``controllers/pk_push.py``).
* Share partners get Web Push only from a kind that declares ``push`` (the
  chat's own filter, ``bemade_portal_kit_chat``): Odoo's record-chatter
  push (``mail.thread``, every model but ``discuss.channel``) skips them.
  Internal users: untouched.
"""
import json
from datetime import datetime, timezone

from odoo import api, models
from odoo.tools.misc import hmac

ENDPOINT_MAX = 2048


class PortalKit(models.AbstractModel):
    _inherit = 'portal.kit'

    @api.model
    def _pk_push_available(self):
        return self._pk_shell_enabled()

    @api.model
    def _pk_push_owner(self, user=None):
        user = user or self.env.user
        return hmac(self.env(su=True), 'bemade_portal_kit_pwa.push_owner', user.partner_id.id)[:32]

    @api.model
    def _pk_push_public_key(self):
        """Odoo's VAPID public key. Odoo's own getter creates the key pair
        only when it is missing (a database that never had one); an
        existing key is never regenerated."""
        return self.env['mail.push.device'].sudo().get_web_push_vapid_public_key()

    @api.model
    def _pk_push_device_state(self, endpoint, user=None):
        """``'mine'``, ``'other'`` (another partner's device) or ``'none'``."""
        if not endpoint:
            return 'none'
        user = user or self.env.user
        device = self.env['mail.push.device'].sudo().search([('endpoint', '=', endpoint)], limit=1)
        if not device:
            return 'none'
        return 'mine' if device.partner_id == user.partner_id else 'other'

    @staticmethod
    def _pk_push_valid(endpoint, keys):
        if not isinstance(endpoint, str) or not endpoint.startswith('https://') or len(endpoint) > ENDPOINT_MAX:
            return False
        return (isinstance(keys, dict) and all(isinstance(keys.get(k), str) and keys.get(k) for k in ('p256dh', 'auth')))

    @api.model
    def _pk_push_register(self, endpoint, keys, expiration_time=None, previous_endpoint=None, enable=False,
                          user=None):
        """Upsert the device ``endpoint`` for ``user`` (default: the current
        user). A previous endpoint is removed only when it is the user's;
        an endpoint registered for another partner moves to the user (one
        device, one person). ``enable`` (an explicit « turn on » click) and
        no device before: every phone-capable kind of the user's app is
        switched on (owner decision). Returns the kinds switched on."""
        user = user or self.env.user
        partner = user.partner_id
        Device = self.env['mail.push.device'].sudo()
        had_device = bool(Device.search_count([('partner_id', '=', partner.id)], limit=1))
        expiration = False
        if expiration_time:
            try:
                expiration = datetime.fromtimestamp(int(float(expiration_time)) / 1000, tz=timezone.utc) \
                    .replace(tzinfo=None)
            except (TypeError, ValueError, OverflowError, OSError):
                expiration = False
        if previous_endpoint and previous_endpoint != endpoint:
            Device.search([('endpoint', '=', previous_endpoint), ('partner_id', '=', partner.id)]).unlink()
        vals = {'keys': json.dumps(keys), 'expiration_time': expiration, 'partner_id': partner.id}
        device = Device.search([('endpoint', '=', endpoint)], limit=1)
        if device:
            device.write(vals)
        else:
            Device.create(dict(vals, endpoint=endpoint))
        kinds = []
        if enable and not had_device:
            kinds = self.pk_notification_push_kinds(self._pk_app(user) or None)
            user._pk_notification_set_push(kinds, True)
        return kinds

    @api.model
    def _pk_push_unregister(self, endpoint, user=None):
        """Remove the device ``endpoint`` when it is the user's (never
        another partner's). Returns whether one was removed."""
        if not endpoint:
            return False
        user = user or self.env.user
        devices = self.env['mail.push.device'].sudo().search(
            [('endpoint', '=', endpoint), ('partner_id', '=', user.partner_id.id)])
        devices.unlink()
        return bool(devices)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_thread_by_web_push(self, message, recipients_data, msg_vals=False, **kwargs):
        if self._name != 'discuss.channel':
            recipients_data = [r for r in recipients_data if not (r.get('share') or r.get('ushare'))]
        return super()._notify_thread_by_web_push(message, recipients_data, msg_vals=msg_vals, **kwargs)
