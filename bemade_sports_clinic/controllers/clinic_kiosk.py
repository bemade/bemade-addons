"""Task 1397 — the clinic sign-in kiosk (public, no patient login).

An iPad at the clinic shows `GET /clinic/kiosk/<token>`: first name, last
name, date of birth, one big button. `POST .../signin` matches the three
values server-side against the clinic's own roster and flips (or creates)
the patient's worklist row to Arrived. The therapist's worklist (#1398) picks
it up within ~20 s.

Law 25 shape — every item here is acceptance-bearing:
* the page shows the clinic name + date and the form — never a roster, a
  count, an autocomplete or a search; after success it shows the signer's OWN
  first name (taken from the matched file, not echoed from the input);
* the date of birth is typed, never displayed back; nothing typed is echoed;
* the token is bound to ONE clinic, to its time window, and is revocable from
  the TP page (`sports.event._kiosk_verify`); invalid, expired and revoked
  tokens all get the SAME "inactive" page;
* nothing is persisted from a failed attempt; no patient is ever created;
* log lines carry ids only (the model does the logging);
* every response is `Cache-Control: no-store` + `X-Robots-Tag: noindex`;
* the public controller never browses a record from user input before the
  token has been verified — the token IS the only input that names a record.

Rate limit: per token (hashed), 10 FAILED attempts per rolling minute, then a
5-minute lockout. Successful sign-ins are not counted — a busy clinic with
twenty players arriving together must never lock its own kiosk. In-memory,
per worker: a multi-worker deployment effectively multiplies the allowance
by the worker count, which is accepted for a kiosk (documented in the
dev-review artifact). No early return on the token's SHAPE: a malformed token
and a revoked one both go through `_kiosk_verify` and answer alike.
"""
import hashlib
import logging
import threading
import time
from collections import OrderedDict, deque
from datetime import date

from odoo import fields, http
from odoo.http import request
from odoo.tools.misc import format_datetime

_logger = logging.getLogger(__name__)

# Seconds before a result screen returns to the form by itself (meta refresh).
KIOSK_RESULT_REFRESH = 8
# Seconds before the "inactive" page re-checks (a kiosk opened early comes
# alive by itself once the window opens; a revoked one never does).
KIOSK_INACTIVE_REFRESH = 60


class KioskRateLimiter:
    """Per-key sliding-window limiter with a lockout.

    ``max_attempts`` failures within ``window`` seconds lock the key for
    ``lockout`` seconds. Bounded LRU so a flood of bogus tokens cannot grow
    memory. Thread-safe (one Odoo worker may serve several threads).
    """

    def __init__(self, max_attempts=10, window=60, lockout=300, max_keys=1000,
                 clock=time.monotonic):
        self.max_attempts = max_attempts
        self.window = window
        self.lockout = lockout
        self.max_keys = max_keys
        self.clock = clock
        self._lock = threading.Lock()
        self._state = OrderedDict()  # key -> {'hits': deque, 'locked_until': float}

    @staticmethod
    def key_for(token):
        return hashlib.sha256((token or '').encode('utf-8')).hexdigest()

    def _entry(self, key):
        entry = self._state.get(key)
        if entry is None:
            entry = {'hits': deque(), 'locked_until': 0.0}
            self._state[key] = entry
            while len(self._state) > self.max_keys:
                self._state.popitem(last=False)
        else:
            self._state.move_to_end(key)
        return entry

    def is_locked(self, key):
        with self._lock:
            entry = self._state.get(key)
            return bool(entry and entry['locked_until'] > self.clock())

    def record_failure(self, key):
        """Count one failed attempt; returns True if the key is NOW locked."""
        with self._lock:
            now = self.clock()
            entry = self._entry(key)
            hits = entry['hits']
            hits.append(now)
            while hits and hits[0] < now - self.window:
                hits.popleft()
            if len(hits) > self.max_attempts:
                entry['locked_until'] = now + self.lockout
                hits.clear()
                return True
            return False

    def reset(self):
        with self._lock:
            self._state.clear()


# Module-level: one limiter per worker process.
kiosk_rate_limiter = KioskRateLimiter()


class ClinicKiosk(http.Controller):

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _no_store(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    def _render(self, template, values, status=200):
        values = dict(values)
        # The result/inactive screens reload by themselves (meta refresh);
        # the form does not.
        values.setdefault('refresh_url', False)
        values.setdefault('refresh_seconds', KIOSK_RESULT_REFRESH)
        response = request.render(template, values, status=status)
        return self._no_store(response)

    def _inactive(self):
        """ONE page for invalid, expired, revoked and out-of-window tokens."""
        return self._render('bemade_sports_clinic.clinic_kiosk_inactive', {
            'refresh_seconds': KIOSK_INACTIVE_REFRESH,
            'refresh_url': request.httprequest.path,
        }, status=404)

    @staticmethod
    def _clinic_values(event, token):
        """What the kiosk may know about the clinic: its name and when."""
        tz_name = request.env['sports.team.digest'].sudo()._resolve_timezone(
            event.team_ids[:1])
        when = format_datetime(
            request.env, event.date_start, tz=tz_name, dt_format='long')
        return {
            'clinic_name': event.name,
            'clinic_when': when,
            'form_url': '/clinic/kiosk/%s' % token,
            'signin_url': '/clinic/kiosk/%s/signin' % token,
            'refresh_seconds': KIOSK_RESULT_REFRESH,
        }

    # ------------------------------------------------------------------
    # routes
    # ------------------------------------------------------------------
    @http.route(['/clinic/kiosk/<string:token>'], type='http', auth='public',
                website=True, sitemap=False, methods=['GET'])
    def clinic_kiosk_form(self, token, **kw):
        event = request.env['sports.event']._kiosk_verify(token)
        if not event:
            return self._inactive()
        values = self._clinic_values(event, token)
        values['incomplete'] = bool(kw.get('incomplete'))
        return self._render('bemade_sports_clinic.clinic_kiosk_form', values)

    @http.route(['/clinic/kiosk/<string:token>/signin'], type='http',
                auth='public', website=True, sitemap=False, methods=['POST'])
    def clinic_kiosk_signin(self, token, **post):
        event = request.env['sports.event']._kiosk_verify(token)
        if not event:
            return self._inactive()
        values = self._clinic_values(event, token)
        key = kiosk_rate_limiter.key_for(token)
        if kiosk_rate_limiter.is_locked(key):
            _logger.info("clinic kiosk: event %s sign-in refused (rate limit)", event.id)
            values.update(outcome='locked', refresh_url=values['form_url'], first_name='')
            return self._render('bemade_sports_clinic.clinic_kiosk_result', values)

        first_name = (post.get('first_name') or '').strip()
        last_name = (post.get('last_name') or '').strip()
        dob_raw = (post.get('date_of_birth') or '').strip()
        date_of_birth = None
        if dob_raw:
            try:
                date_of_birth = fields.Date.to_date(dob_raw)
            except ValueError:
                date_of_birth = None
        if not first_name or not last_name:
            # Incomplete form: back to the form with a hint, nothing echoed.
            return request.redirect(values['form_url'] + '?incomplete=1')
        if date_of_birth is not None and not isinstance(date_of_birth, date):
            date_of_birth = None

        outcome, patient = request.env['sports.clinic.attendance'].sudo()._kiosk_sign_in(
            event, first_name, last_name, date_of_birth)
        if outcome == 'unknown' and kiosk_rate_limiter.record_failure(key):
            _logger.info("clinic kiosk: event %s locked (rate limit)", event.id)
            outcome = 'locked'
        values['outcome'] = outcome
        values['refresh_url'] = values['form_url']
        # Only the matched file's own first name, only on success.
        values['first_name'] = patient.first_name if outcome == 'ok' else ''
        return self._render('bemade_sports_clinic.clinic_kiosk_result', values)
