"""Task 1433 — the kiosk DEVICE: reversed pairing for the clinic sign-in iPad.

The #1397/#1419 kiosk was entered through a per-clinic signed URL (QR code).
A supervised iPad web clip cannot scan a QR, has no address bar and keeps its
cookies until the profile is reinstalled — so the pairing is reversed: the
device loads ONE stable URL (`/clinic/kiosk`) forever, the server mints it an
identity (this model) behind a long-lived HttpOnly cookie, and the THERAPIST
types the device's on-screen pairing code into their portal clinic page to
bind the device to a clinic. Nobody ever touches the iPad.

Secrets, hashed only:

* the device token — the raw value lives ONLY in the device's cookie; the
  database stores its SHA-256 (`token_hash`). Revocation = rotating the hash:
  the cookie stops verifying, and the next load mints a FRESH device whose
  Set-Cookie overwrites the old one (that is how revocation works despite
  un-clearable web-clip cookies).
* the pairing code — 6 characters over an unambiguous alphabet (no 0/O/1/I),
  5-minute TTL, auto-regenerating. Only its SHA-256 is stored; the raw code
  is DERIVED deterministically from (device id, expiry) with `odoo.tools.hmac`
  keyed on `database.secret`, so re-rendering the pairing screen within the
  TTL shows the SAME code without ever persisting it (the noscript 30 s
  meta-refresh path depends on that stability).

Law 25 shape: a device knows nothing until it is bound; log lines carry ids
only; the pairing chatter notes on the clinic carry ids only.
"""
import hashlib
import logging
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools.misc import consteq
from odoo.tools.misc import hmac as hmac_sign

_logger = logging.getLogger(__name__)

# Raw device token entropy (urlsafe base64 of this many random bytes).
TOKEN_BYTES = 32
# Pairing code: 6 chars over a 32-char alphabet without 0/O/1/I — a therapist
# reads it off the iPad and types it; every character must be unambiguous.
PAIRING_CODE_LENGTH = 6
PAIRING_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
PAIRING_CODE_TTL = timedelta(minutes=5)
# HMAC scope for the deterministic pairing-code derivation (cannot be mistaken
# for any other odoo.tools.hmac user).
PAIRING_HMAC_SCOPE = 'bemade_sports_clinic.kiosk_pairing_code'
# last_seen_at write throttle: the pairing screen polls every ~4 s; one write
# per minute is plenty for a « last seen » display.
LAST_SEEN_THROTTLE = timedelta(seconds=60)


class SportsClinicKioskDevice(models.Model):
    _name = 'sports.clinic.kiosk.device'
    _description = 'Clinic Kiosk Device'
    _order = 'id desc'

    name = fields.Char(
        required=True,
        help='Display name of the physical device (renamable), e.g. '
             '« Borne A1F3 ». Defaults to a short random suffix at issue time.')
    token_hash = fields.Char(
        index=True, readonly=True, copy=False,
        help='SHA-256 of the device token. The raw token exists only in the '
             'device cookie, never in the database. Rotated by Revoke.')
    clinic_id = fields.Many2one(
        'sports.event', string='Bound Clinic', ondelete='set null', index=True,
        help='Clinic this device is currently bound to. Several devices may '
             'be bound to the same clinic simultaneously.')
    bound_until = fields.Datetime(
        help='End of the binding: the clinic window end at pairing time. Past '
             'this moment the device falls back to the pairing screen by '
             'itself.')
    last_seen_at = fields.Datetime(
        readonly=True,
        help='Last time the device presented its token (throttled to about '
             'one update per minute).')
    pairing_code_hash = fields.Char(
        readonly=True, copy=False,
        help='SHA-256 of the current pairing code; empty when bound or when '
             'no code was issued yet.')
    pairing_code_expiry = fields.Datetime(readonly=True, copy=False)
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # hashing / code derivation
    # ------------------------------------------------------------------
    @staticmethod
    def _hash_raw(raw):
        return hashlib.sha256((raw or '').encode('utf-8')).hexdigest()

    def _pairing_code_for(self, expiry):
        """The pairing code of THIS device for THAT expiry — deterministic
        (HMAC over (id, expiry) keyed on database.secret), so the code can be
        re-displayed within its TTL without storing the raw value."""
        self.ensure_one()
        digest = hmac_sign(self.env(su=True), PAIRING_HMAC_SCOPE,
                           (int(self.id), fields.Datetime.to_string(expiry)))
        value = int(digest, 16)
        chars = []
        for _i in range(PAIRING_CODE_LENGTH):
            value, index = divmod(value, len(PAIRING_CODE_ALPHABET))
            chars.append(PAIRING_CODE_ALPHABET[index])
        return ''.join(chars)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    @api.model
    def _issue(self):
        """Mint a fresh device: create the row, return ``(device, raw_token)``.
        The raw token goes into the Set-Cookie and is never stored. The caller
        (the public dispatcher) is IP-rate-limited."""
        raw = secrets.token_urlsafe(TOKEN_BYTES)
        device = self.sudo().create({
            'name': 'Borne %s' % secrets.token_hex(2).upper(),
            'token_hash': self._hash_raw(raw),
        })
        _logger.info("clinic kiosk: device %s issued", device.id)
        return device, raw

    @api.model
    def _verify_token(self, raw):
        """Resolve a raw cookie token to its ACTIVE device, or an empty
        recordset. Constant-time compare on the hash; updates ``last_seen_at``
        (throttled). Returns a sudo() recordset — the caller is public."""
        Device = self.sudo()
        if not raw or not isinstance(raw, str) or len(raw) > 256:
            return Device.browse()
        token_hash = self._hash_raw(raw)
        device = Device.search([
            ('token_hash', '=', token_hash), ('active', '=', True)], limit=1)
        if not device or not consteq(device.token_hash or '', token_hash):
            return Device.browse()
        now = fields.Datetime.now()
        if not device.last_seen_at or now - device.last_seen_at > LAST_SEEN_THROTTLE:
            device.write({'last_seen_at': now})
        return device

    def _current_pairing_code(self, now=None):
        """The device's live pairing code — the stored one while its TTL
        holds (re-derived, never read from the DB), a fresh one otherwise.
        Collisions among unexpired codes are regenerated away by bumping the
        expiry a second at a time (6 chars over 32: vanishingly rare)."""
        self.ensure_one()
        device = self.sudo()
        now = now or fields.Datetime.now()
        if device.pairing_code_hash and device.pairing_code_expiry and \
                now < device.pairing_code_expiry:
            return device._pairing_code_for(device.pairing_code_expiry)
        expiry = now + PAIRING_CODE_TTL
        code = None
        for _attempt in range(10):
            candidate = device._pairing_code_for(expiry)
            candidate_hash = self._hash_raw(candidate)
            clash = device.search_count([
                ('id', '!=', device.id),
                ('pairing_code_hash', '=', candidate_hash),
                ('pairing_code_expiry', '>', now)])
            if not clash:
                code = candidate
                break
            expiry += timedelta(seconds=1)
        if code is None:  # 10 straight collisions: not credible, but never 500
            code = device._pairing_code_for(expiry)
            candidate_hash = self._hash_raw(code)
            _logger.warning("clinic kiosk: device %s pairing code collision "
                            "fallback", device.id)
        device.write({'pairing_code_hash': candidate_hash,
                      'pairing_code_expiry': expiry})
        return code

    def _pairing_code_seconds_left(self, now=None):
        """Whole seconds before the current code expires (0 when none)."""
        self.ensure_one()
        device = self.sudo()
        now = now or fields.Datetime.now()
        if not device.pairing_code_expiry or device.pairing_code_expiry <= now:
            return 0
        return int((device.pairing_code_expiry - now).total_seconds())

    @api.model
    def _pair(self, code, clinic):
        """Portal side: match an UNEXPIRED pairing code, bind that device to
        ``clinic`` until the clinic window ends, clear the code. Returns the
        device, or an empty recordset when the code is unknown/expired.
        The caller has already gated the user (`_can_manage_kiosk`)."""
        Device = self.sudo()
        code = (code or '').strip().upper().replace(' ', '').replace('-', '')
        if len(code) != PAIRING_CODE_LENGTH or \
                any(c not in PAIRING_CODE_ALPHABET for c in code):
            return Device.browse()
        now = fields.Datetime.now()
        code_hash = self._hash_raw(code)
        device = Device.search([
            ('pairing_code_hash', '=', code_hash),
            ('pairing_code_expiry', '>', now),
            ('active', '=', True)], limit=1)
        if not device or not consteq(device.pairing_code_hash or '', code_hash):
            return Device.browse()
        clinic = clinic.sudo()
        _start, end = clinic._kiosk_window()
        device.write({
            'clinic_id': clinic.id,
            'bound_until': end,
            'pairing_code_hash': False,
            'pairing_code_expiry': False,
        })
        clinic.message_post(
            body=_("Sign-in kiosk device #%(device)s paired (clinic #%(clinic)s).",
                   device=device.id, clinic=clinic.id),
            message_type='comment', subtype_xmlid='mail.mt_note')
        _logger.info("clinic kiosk: device %s paired to event %s by user %s",
                     device.id, clinic.id, self.env.user.id)
        return device

    def _unbind(self):
        """Detach from the clinic (« Dissocier »). The device keeps its token
        and falls back to the pairing screen on its next poll/load."""
        for device in self.sudo():
            clinic = device.clinic_id
            device.write({'clinic_id': False, 'bound_until': False})
            if clinic:
                clinic.message_post(
                    body=_("Sign-in kiosk device #%(device)s unbound "
                           "(clinic #%(clinic)s).",
                           device=device.id, clinic=clinic.id),
                    message_type='comment', subtype_xmlid='mail.mt_note')
            _logger.info("clinic kiosk: device %s unbound by user %s",
                         device.id, self.env.user.id)
        return True

    def _revoke(self):
        """Rotate the token hash: the cookie out there stops verifying at
        once. The physical device's next load mints a FRESH device row and
        its Set-Cookie overwrites the dead cookie — that is the revocation
        path for a web clip whose cookies cannot be cleared."""
        for device in self.sudo():
            device.write({
                'token_hash': self._hash_raw(secrets.token_urlsafe(TOKEN_BYTES)),
                'clinic_id': False,
                'bound_until': False,
                'pairing_code_hash': False,
                'pairing_code_expiry': False,
            })
            _logger.info("clinic kiosk: device %s token revoked by user %s",
                         device.id, self.env.user.id)
        return True

    def _is_bound(self):
        """Bound AND usable right now: a clinic is set, the binding has not
        expired, and the clinic window (`_kiosk_window` semantics, on the
        clinic's CURRENT dates) is open."""
        self.ensure_one()
        device = self.sudo()
        clinic = device.clinic_id
        if not clinic or not device.bound_until:
            return False
        now = fields.Datetime.now()
        if now > device.bound_until:
            return False
        if clinic.event_type != 'clinic':
            return False
        start, end = clinic._kiosk_window()
        return start <= now <= end

    # ------------------------------------------------------------------
    # backend buttons
    # ------------------------------------------------------------------
    def action_unbind(self):
        return self._unbind()

    def action_revoke_token(self):
        return self._revoke()

    # ------------------------------------------------------------------
    # housekeeping
    # ------------------------------------------------------------------
    @api.model
    def _cron_purge_unpaired_devices(self):
        """Daily: drop device rows that never got paired and are older than
        24 h — drive-by hits on the public dispatcher must not accumulate
        rows. Exactly the plan's predicate (clinic unset, created > 1 day
        ago): a NAMED device sitting unbound for a day is re-minted on its
        next load (it was on the pairing screen anyway), only the given name
        is lost."""
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        devices = self.with_context(active_test=False).sudo().search([
            ('clinic_id', '=', False),
            ('bound_until', '=', False),
            ('create_date', '<', cutoff),
        ])
        count = len(devices)
        if devices:
            devices.unlink()
            _logger.info("clinic kiosk: purged %s never-paired device rows", count)
        return count
