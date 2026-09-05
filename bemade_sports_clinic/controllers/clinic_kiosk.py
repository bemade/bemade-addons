"""Task 1397/1433 — the clinic sign-in kiosk (public, no patient login).

Task 1433 reversed the pairing. The iPad (supervised full-screen web clip: no
address bar, no back button, cookies not clearable without reinstalling the
profile) loads exactly ONE stable URL forever: ``GET /clinic/kiosk``. On first
load the server mints a `sports.clinic.kiosk.device` and a long-lived random
token stored in an ``HttpOnly; SameSite=Lax`` cookie (Secure over https) — the
only persistent state on the device. An unbound device shows a 6-character
pairing code; the therapist — authenticated in the PORTAL — types it into the
kiosk card of `/my/clinic/<id>`, and the kiosk transitions to the sign-in flow
by itself (a ~4 s JSON poll, meta-refresh fallback with JS off). The old
per-clinic signed-URL routes (`/clinic/kiosk/<token>`) are gone.

Law 25 shape — every item here is acceptance-bearing:
* the page shows the clinic name + date and the form — never a roster, a
  count, an autocomplete or a search; after a sign-in the answer is ONE
  generic welcome (#1418 queues a no-match behind the SAME screen, and since
  #1433 the POST-Redirect-GET result carries no name at all, so the answer
  never tells a known name from an unknown one);
* the date of birth is typed, never displayed back;
* the device is bound to ONE clinic, to its time window, and revocable
  (portal « Dissocier » unbinds; backend Revoke rotates the token);
* no patient is ever created from the kiosk (#1418 queues unregistered rows);
* log lines carry ids only (the models do the logging);
* every response is `Cache-Control: no-store, no-cache, must-revalidate` +
  `Pragma: no-cache` + `X-Robots-Tag: noindex` — the poll included;
* nothing kiosk-related ever touches localStorage/sessionStorage;
* PRG: the sign-in POST answers `303 → /clinic/kiosk?done=<flag>` (non-PII
  flags only), so back/reload can never resubmit;
* the kiosk renders FRENCH regardless of the browser/OS language; « English »
  is a per-request query param that resets for each fresh visitor.

Rate limits (in-memory, per worker — a multi-worker deployment effectively
multiplies the allowance by the worker count, accepted for a kiosk since
#1397): sign-in misses are limited per DEVICE (10 failed attempts per rolling
minute, then a 5-minute lockout; successful sign-ins are never counted — a
busy clinic must not lock its own kiosk), and device MINTING is limited per
IP (a cookie-less crawler hammering the public dispatcher must not fill the
table — the daily purge cron is the second belt).
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

# The ONE device cookie. Scoped to the kiosk path so the rest of the site
# never sees it. ~2 years: effectively « forever » for a web clip.
KIOSK_COOKIE = 'clinic_kiosk_device'
KIOSK_COOKIE_MAX_AGE = 2 * 365 * 24 * 3600
# Seconds before a result screen returns to the form by itself (meta refresh).
KIOSK_RESULT_REFRESH = 8
# Seconds before the "inactive" page re-checks.
KIOSK_INACTIVE_REFRESH = 60
# Pairing screen: JS poll cadence, and the noscript meta-refresh fallback.
KIOSK_POLL_SECONDS = 4
KIOSK_PAIRING_REFRESH = 30
# Idle timeout (seconds) before the sign-in form abandons back to the
# dispatcher; ir.config_parameter override below.
KIOSK_IDLE_DEFAULT = 75
KIOSK_IDLE_PARAM = 'bemade_sports_clinic.kiosk_idle_seconds'
# The kiosk renders French, whatever the device/browser says.
KIOSK_FORCED_LANG = 'fr_CA'
# The PRG result flags — never anything else on the query string.
KIOSK_DONE_FLAGS = ('ok', 'duplicate', 'locked', 'unknown')


class KioskRateLimiter:
    """Per-key sliding-window limiter with a lockout.

    ``max_attempts`` failures within ``window`` seconds lock the key for
    ``lockout`` seconds. Bounded LRU so a flood of bogus keys cannot grow
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
# Sign-in misses, keyed on the device token hash (#1397 semantics, re-keyed).
kiosk_rate_limiter = KioskRateLimiter()
# Device minting, keyed on the client IP: 20 fresh devices per rolling minute
# per IP, then a 5-minute lockout (the inactive page).
kiosk_mint_limiter = KioskRateLimiter(max_attempts=20, window=60, lockout=300)


class ClinicKiosk(http.Controller):

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _no_store(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    @staticmethod
    def _force_lang(kw):
        """French, whatever the browser/website says; ?lang=en flips ONE
        request to English (carried through the flow by links/hidden input,
        never persisted — the return to /clinic/kiosk resets it)."""
        lang = 'en_US' if kw.get('lang') == 'en' else KIOSK_FORCED_LANG
        installed = [code for code, _name in
                     request.env['res.lang'].sudo().get_installed()]
        if lang not in installed:
            lang = request.env.lang if request.env.lang in installed else 'en_US'
        request.update_context(lang=lang)
        return lang

    @staticmethod
    def _lang_query(kw):
        """The query fragment that carries the EN toggle through PRG."""
        return 'lang=en' if kw.get('lang') == 'en' else ''

    @staticmethod
    def _idle_seconds():
        try:
            value = int(request.env['ir.config_parameter'].sudo().get_param(
                KIOSK_IDLE_PARAM, KIOSK_IDLE_DEFAULT))
        except (TypeError, ValueError):
            value = KIOSK_IDLE_DEFAULT
        return value if value > 0 else KIOSK_IDLE_DEFAULT

    @staticmethod
    def _device():
        """The device presenting the cookie, or an empty recordset."""
        raw = request.httprequest.cookies.get(KIOSK_COOKIE)
        return request.env['sports.clinic.kiosk.device']._verify_token(raw)

    def _render(self, template, values, status=200):
        values = dict(values)
        values.setdefault('refresh_url', False)
        values.setdefault('refresh_seconds', KIOSK_RESULT_REFRESH)
        values.setdefault('noscript_refresh_url', False)
        values.setdefault('noscript_refresh_seconds', KIOSK_PAIRING_REFRESH)
        values.setdefault('idle_seconds', False)
        values.setdefault('kiosk_lang', request.env.lang)
        response = request.render(template, values, status=status)
        return self._no_store(response)

    def _inactive(self):
        """ONE page for every refused dispatcher hit (e.g. mint flood)."""
        return self._render('bemade_sports_clinic.clinic_kiosk_inactive', {
            'refresh_seconds': KIOSK_INACTIVE_REFRESH,
            'refresh_url': '/clinic/kiosk',
        }, status=404)

    @staticmethod
    def _clinic_values(event, kw):
        """What the kiosk may know about the clinic: its name and when."""
        tz_name = request.env['sports.team.digest'].sudo()._resolve_timezone(
            event.team_ids[:1])
        when = format_datetime(
            request.env, event.date_start, tz=tz_name, dt_format='long')
        lang_query = ClinicKiosk._lang_query(kw)
        return {
            'clinic_name': event.name,
            'clinic_when': when,
            'form_url': '/clinic/kiosk' + ('?' + lang_query if lang_query else ''),
            'signin_url': '/clinic/kiosk/signin',
            'home_url': '/clinic/kiosk',
            'lang_en': bool(lang_query),
            'refresh_seconds': KIOSK_RESULT_REFRESH,
        }

    def _pairing(self, device, kw):
        """The pairing screen: the giant code, the poll script, the noscript
        fallback. Clinic-agnostic — an unbound device knows nothing."""
        code = device._current_pairing_code()
        return self._render('bemade_sports_clinic.clinic_kiosk_pairing', {
            'pairing_code': code,
            'code_seconds_left': device._pairing_code_seconds_left(),
            'poll_seconds': KIOSK_POLL_SECONDS,
            'noscript_refresh_url': '/clinic/kiosk',
            'noscript_refresh_seconds': KIOSK_PAIRING_REFRESH,
            'home_url': '/clinic/kiosk',
            'lang_en': bool(self._lang_query(kw)),
        })

    # ------------------------------------------------------------------
    # routes
    # ------------------------------------------------------------------
    # multilang=False on every kiosk route: the website layer must NEVER
    # 303 the kiosk to /<lang>/clinic/kiosk — the device cookie is scoped
    # Path=/clinic/kiosk, so a lang-prefixed URL arrives cookie-less and
    # mints a fresh device on every load (found on the 1433 UAT: an English
    # browser was bounced to /en/clinic/kiosk and the kiosk re-paired
    # forever). It also keeps url_for from prefixing the in-page kiosk
    # links/actions. The kiosk forces its own language server-side anyway.
    @http.route(['/clinic/kiosk'], type='http', auth='public',
                website=True, sitemap=False, methods=['GET'],
                multilang=False)
    def clinic_kiosk_dispatch(self, **kw):
        """The ONE stable kiosk URL — a tiny state machine:

        no/invalid cookie  -> mint a device (IP rate-limited) + Set-Cookie
                              -> pairing screen
        unbound / expired  -> pairing screen (current code)
        bound + in window  -> sign-in form; ?done=<flag> -> result screen
        """
        self._force_lang(kw)
        device = self._device()
        raw_to_set = None
        if not device:
            ip_key = kiosk_mint_limiter.key_for(
                request.httprequest.remote_addr or '')
            if kiosk_mint_limiter.is_locked(ip_key) or \
                    kiosk_mint_limiter.record_failure(ip_key):
                _logger.info("clinic kiosk: device mint refused (rate limit)")
                return self._inactive()
            device, raw_to_set = request.env[
                'sports.clinic.kiosk.device']._issue()

        if device._is_bound():
            values = self._clinic_values(device.clinic_id, kw)
            done = kw.get('done')
            if done in KIOSK_DONE_FLAGS:
                values.update(outcome=done, refresh_url='/clinic/kiosk')
                response = self._render(
                    'bemade_sports_clinic.clinic_kiosk_result', values)
            else:
                values['incomplete'] = bool(kw.get('incomplete'))
                values['idle_seconds'] = self._idle_seconds()
                # noscript fallback: abandon the form back to the dispatcher
                # after the same idle window (JS path resets on interaction).
                values['noscript_refresh_url'] = '/clinic/kiosk'
                values['noscript_refresh_seconds'] = values['idle_seconds']
                response = self._render(
                    'bemade_sports_clinic.clinic_kiosk_form', values)
        else:
            response = self._pairing(device, kw)

        if raw_to_set:
            response.set_cookie(
                KIOSK_COOKIE, raw_to_set,
                max_age=KIOSK_COOKIE_MAX_AGE,
                path='/clinic/kiosk',
                httponly=True,
                samesite='Lax',
                secure=request.httprequest.scheme == 'https')
        return response

    @http.route(['/clinic/kiosk/poll'], type='http', auth='public',
                sitemap=False, methods=['GET'], multilang=False)
    def clinic_kiosk_poll(self, **kw):
        """`{"bound": bool}` for the device cookie: true once the device is
        bound AND its clinic window is open — the pairing screen then
        replaces itself with the dispatcher. Never mints a device."""
        device = self._device()
        response = request.make_json_response(
            {'bound': bool(device and device._is_bound())})
        return self._no_store(response)

    @http.route(['/clinic/kiosk/signin'], type='http', auth='public',
                website=True, sitemap=False, methods=['POST'],
                multilang=False)
    def clinic_kiosk_signin(self, **post):
        """The sign-in POST, device-cookie authenticated. Always answers
        303 → /clinic/kiosk (PRG): reload or back can never resubmit."""
        self._force_lang(post)
        lang_query = self._lang_query(post)

        def _redirect(*params):
            parts = [p for p in params if p]
            if lang_query:
                parts.append(lang_query)
            url = '/clinic/kiosk' + ('?' + '&'.join(parts) if parts else '')
            return request.redirect(url, code=303)

        device = self._device()
        if not device or not device._is_bound():
            return _redirect()
        clinic = device.clinic_id
        key = kiosk_rate_limiter.key_for(device.token_hash)
        if kiosk_rate_limiter.is_locked(key):
            _logger.info("clinic kiosk: event %s sign-in refused (rate limit,"
                         " device %s)", clinic.id, device.id)
            return _redirect('done=locked')

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
            return _redirect('incomplete=1')
        if date_of_birth is not None and not isinstance(date_of_birth, date):
            date_of_birth = None

        outcome, patient = request.env[
            'sports.clinic.attendance'].sudo()._kiosk_sign_in(
                clinic, first_name, last_name, date_of_birth)
        # #1418: an empty patient means NO file matched — the model queued the
        # typed identity (or found it already queued) and answers like a
        # normal sign-in; the attempt still counts as a miss for the limiter.
        if not patient and kiosk_rate_limiter.record_failure(key):
            _logger.info("clinic kiosk: event %s locked (rate limit, device"
                         " %s)", clinic.id, device.id)
            outcome = 'locked'
        return _redirect('done=%s' % outcome)
