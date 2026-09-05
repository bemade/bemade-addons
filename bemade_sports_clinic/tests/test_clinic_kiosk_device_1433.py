"""Task 1433 — reversed kiosk pairing: the device model + the dispatcher.

Acceptance covered here (everything that is not browser-driven; the REAL
device click-through — pairing end-to-end without touching the iPad, the
back-gesture/bfcache behaviour, the idle reset firing, the on-screen-keyboard
layout, the phone-width portal card — is for /dev-review and deliberately
NOT claimed from these tests):

* device issuance on first load + the cookie attributes (HttpOnly,
  SameSite=Lax, Max-Age ~2 years, Path=/clinic/kiosk; Secure is bound to the
  request scheme — https in prod/staging, plain http in the test server);
* pairing code: 5-min TTL, stable within it (the noscript refresh must
  re-show the SAME code), regenerated after expiry, collision regenerated
  away, unambiguous alphabet (no 0/O/1/I);
* _pair / _unbind / _revoke / auto-expiry at bound_until / clinic window;
* the dispatcher state machine: mint -> pairing -> (pair) -> form ->
  ?done=<flag> result -> auto-return; expired binding -> pairing again;
  revoked device -> fresh identity;
* the poll endpoint ({'bound': bool}, no-store, never mints);
* PRG: the sign-in POST answers 303, the result URL is re-loadable without
  writing anything;
* rate limit: device minting per IP (the sign-in per-device lockout is in
  test_clinic_kiosk.py);
* forced-French rendering regardless of Accept-Language, WITHOUT any
  frontend_lang cookie (that is the feature); the EN toggle as a per-request
  param whose return-to-start resets to French;
* no-store + Pragma headers on EVERY kiosk response;
* no off-domain link and no web-storage use on any kiosk screen;
* the old /clinic/kiosk/<token> routes are gone;
* the never-paired purge cron; system-only ACL on the device model.

All fixtures are synthetic: this addon's repository is public.
"""
import hashlib
import re
from datetime import date, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from odoo.addons.bemade_sports_clinic.controllers.clinic_kiosk import (
    KIOSK_COOKIE, kiosk_mint_limiter, kiosk_rate_limiter)
from odoo.addons.bemade_sports_clinic.models.sports_clinic_kiosk_device import (
    PAIRING_CODE_ALPHABET, PAIRING_CODE_LENGTH)

IDLE_PARAM = 'bemade_sports_clinic.kiosk_idle_seconds'


@tagged('-at_install', 'post_install')
class TestClinicKioskDevice(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'])

        cls.org = env['res.partner'].create({'name': 'KD Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'KD Team', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'KD Therapist', 'login': 'kd.tp@example.com', 'password': 'kd-tp',
            'group_ids': [Command.set([portal_g, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team.id, 'partner_id': cls.tp.partner_id.id,
            'role': 'therapist'})

        cls.kim = env['sports.patient'].create({
            'first_name': 'Kim', 'last_name': 'Device',
            'date_of_birth': date(2001, 2, 3)})
        cls.kim.team_ids = [Command.set([cls.team.id])]

        now = fields.Datetime.now()
        cls.clinic = cls._make_event('KD Clinic Now', now - timedelta(minutes=30))
        cls.clinic_future = cls._make_event('KD Clinic Later',
                                            now + timedelta(days=7))
        cls.Device = env['sports.clinic.kiosk.device']
        cls.Attendance = env['sports.clinic.attendance']

    @classmethod
    def _make_event(cls, name, start):
        return cls.env['sports.event'].create({
            'name': name, 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })

    def setUp(self):
        super().setUp()
        kiosk_rate_limiter.reset()
        kiosk_mint_limiter.reset()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _clear_kiosk_cookie(self):
        jar = self.opener.cookies
        for cookie in list(jar):
            if cookie.name == KIOSK_COOKIE:
                jar.clear(cookie.domain, cookie.path, cookie.name)

    def _mint(self):
        """Fresh device via the dispatcher; returns (response, device)."""
        self._clear_kiosk_cookie()
        resp = self.url_open('/clinic/kiosk')
        return resp, self.Device.search([], order='id desc', limit=1)

    def _bind(self, event=None):
        _resp, device = self._mint()
        self.Device._pair(device._current_pairing_code(), event or self.clinic)
        return device

    def _cookie_value(self):
        for cookie in self.opener.cookies:
            if cookie.name == KIOSK_COOKIE:
                return cookie.value
        return None

    def _csrf_from(self, html):
        match = re.search(r'csrf_token:\s*"([^"]+)"', html)
        return match.group(1) if match else ''

    def _assert_no_store(self, resp):
        self.assertEqual(resp.headers.get('Cache-Control'),
                         'no-store, no-cache, must-revalidate')
        self.assertEqual(resp.headers.get('Pragma'), 'no-cache')

    # ==================================================================
    # ISSUANCE + COOKIE
    # ==================================================================
    def test_issue_and_cookie_attributes(self):
        before = self.Device.search_count([])
        resp, device = self._mint()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.Device.search_count([]), before + 1)
        # the pairing screen, not a form
        self.assertNotIn('name="first_name"', resp.text)
        self._assert_no_store(resp)
        # cookie attributes
        set_cookie = resp.headers.get('Set-Cookie', '')
        self.assertIn(KIOSK_COOKIE + '=', set_cookie)
        self.assertIn('HttpOnly', set_cookie)
        self.assertIn('SameSite=Lax', set_cookie)
        self.assertIn('Path=/clinic/kiosk', set_cookie)
        self.assertIn('Max-Age=63072000', set_cookie, "~2 years")
        # Secure is scheme-bound: the test server is plain http, so not set
        # here; over https (prod/staging/local dev TLS) it is.
        # the raw token lives in the cookie only; the DB has its SHA-256
        raw = self._cookie_value()
        self.assertTrue(raw)
        self.assertNotEqual(raw, device.token_hash)
        self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(), device.token_hash)
        # a second load with the cookie mints NOTHING
        again = self.url_open('/clinic/kiosk')
        self.assertEqual(again.status_code, 200)
        self.assertEqual(self.Device.search_count([]), before + 1)
        self.assertNotIn(KIOSK_COOKIE + '=', again.headers.get('Set-Cookie', ''),
                         "no new cookie on a known device")
        # device name defaults to « Borne <suffix> »
        self.assertTrue(device.name.startswith('Borne '))

    def test_verify_token(self):
        _resp, device = self._mint()
        raw = self._cookie_value()
        self.assertEqual(self.Device._verify_token(raw), device)
        self.assertTrue(device.last_seen_at)
        for garbage in (None, '', 'x', 'a' * 500, raw[:-2] + 'zz'):
            self.assertFalse(self.Device._verify_token(garbage))
        device.action_archive()
        self.assertFalse(self.Device._verify_token(raw), "archived device is dead")

    # ==================================================================
    # PAIRING CODE
    # ==================================================================
    def test_pairing_code_shape_ttl_and_stability(self):
        _resp, device = self._mint()
        code = device._current_pairing_code()
        self.assertEqual(len(code), PAIRING_CODE_LENGTH)
        self.assertTrue(all(c in PAIRING_CODE_ALPHABET for c in code))
        for ambiguous in '01OI':
            self.assertNotIn(ambiguous, PAIRING_CODE_ALPHABET)
        # stable within the TTL: the noscript 30 s refresh re-shows the SAME
        # code (nothing raw is stored — it is re-derived)
        self.assertEqual(device._current_pairing_code(), code)
        expiry = device.pairing_code_expiry
        self.assertTrue(expiry)
        self.assertEqual(
            device.pairing_code_hash,
            hashlib.sha256(code.encode()).hexdigest())
        left = device._pairing_code_seconds_left()
        self.assertTrue(0 < left <= 300, "5-minute TTL")
        # expired: a fresh code, a fresh expiry
        device.sudo().write({
            'pairing_code_expiry': fields.Datetime.now() - timedelta(seconds=1)})
        renewed = device._current_pairing_code()
        self.assertGreater(device.pairing_code_expiry, expiry - timedelta(minutes=1))
        self.assertEqual(
            device.pairing_code_hash,
            hashlib.sha256(renewed.encode()).hexdigest())

    def test_pairing_code_collision_is_regenerated_away(self):
        _r1, device_a = self._mint()
        _r2, device_b = self._mint()
        # drop A's live code (the mint rendered one) so the call below takes
        # the REGENERATION path and must dodge the planted collision
        device_a.sudo().write({'pairing_code_hash': False,
                               'pairing_code_expiry': False})
        now = fields.Datetime.now().replace(microsecond=0)
        expiry = now + timedelta(minutes=5)
        # plant B's live code as EXACTLY what A would derive for that expiry
        colliding = device_a._pairing_code_for(expiry)
        device_b.sudo().write({
            'pairing_code_hash': hashlib.sha256(colliding.encode()).hexdigest(),
            'pairing_code_expiry': expiry,
        })
        code_a = device_a._current_pairing_code(now=now)
        self.assertNotEqual(code_a, colliding, "collision bumped away")
        self.assertGreater(device_a.pairing_code_expiry, expiry)

    # ==================================================================
    # PAIR / UNBIND / REVOKE / EXPIRY (model)
    # ==================================================================
    def test_pair_binds_until_the_window_end_and_clears_the_code(self):
        _resp, device = self._mint()
        code = device._current_pairing_code()
        # garbage shapes never pair
        for bad in (None, '', 'ABC', 'ABCDEFG', 'ABC0DE', code[:-1] + '0'):
            self.assertFalse(self.Device._pair(bad, self.clinic))
        paired = self.Device._pair(code, self.clinic)
        self.assertEqual(paired, device)
        self.assertEqual(device.clinic_id, self.clinic)
        _start, end = self.clinic._kiosk_window()
        self.assertEqual(device.bound_until, end)
        self.assertFalse(device.pairing_code_hash, "code cleared on pair")
        self.assertFalse(device.pairing_code_expiry)
        self.assertTrue(device._is_bound())
        # the SAME code cannot pair a second device
        self.assertFalse(self.Device._pair(code, self.clinic))
        # an expired code cannot pair
        _resp, device2 = self._mint()
        code2 = device2._current_pairing_code()
        device2.sudo().write({
            'pairing_code_expiry': fields.Datetime.now() - timedelta(seconds=1)})
        self.assertFalse(self.Device._pair(code2, self.clinic))
        # several devices on ONE clinic simultaneously is fine
        code2 = device2._current_pairing_code()
        self.assertEqual(self.Device._pair(code2, self.clinic), device2)
        self.assertTrue(device._is_bound() and device2._is_bound())

    def test_unbind_revoke_and_auto_expiry(self):
        device = self._bind()
        self.assertTrue(device._is_bound())
        # auto-expiry at bound_until
        device.sudo().write({
            'bound_until': fields.Datetime.now() - timedelta(seconds=1)})
        self.assertFalse(device._is_bound())
        # re-pair, then unbind
        code = device._current_pairing_code()
        self.Device._pair(code, self.clinic)
        self.assertTrue(device._is_bound())
        device._unbind()
        self.assertFalse(device.clinic_id)
        self.assertFalse(device.bound_until)
        # revoke rotates the token hash: the cookie dies
        raw = self._cookie_value()
        self.assertEqual(self.Device._verify_token(raw), device)
        old_hash = device.token_hash
        device._revoke()
        self.assertNotEqual(device.token_hash, old_hash)
        self.assertFalse(self.Device._verify_token(raw))

    def test_binding_respects_the_clinic_window(self):
        """Paired to a clinic whose window is not open: NOT usable (the
        kiosk stays on / falls back to the pairing screen)."""
        device = self._bind(self.clinic_future)
        self.assertEqual(device.clinic_id, self.clinic_future)
        self.assertFalse(device._is_bound(), "window not open yet")

    # ==================================================================
    # DISPATCHER STATE MACHINE + POLL
    # ==================================================================
    def test_dispatcher_state_machine(self):
        # 1. no cookie -> mint + pairing (French)
        resp, device = self._mint()
        self.assertIn('code', resp.text.lower())
        self.assertIn(device._current_pairing_code(), resp.text)
        self.assertIn('Demandez à votre thérapeute', resp.text)
        # 2. poll: not bound yet
        poll = self.url_open('/clinic/kiosk/poll')
        self.assertEqual(poll.json(), {'bound': False})
        self._assert_no_store(poll)
        # 3. pair -> poll flips -> the dispatcher serves the form
        self.Device._pair(device._current_pairing_code(), self.clinic)
        self.assertEqual(self.url_open('/clinic/kiosk/poll').json(), {'bound': True})
        form = self.url_open('/clinic/kiosk')
        self.assertIn('KD Clinic Now', form.text)
        self.assertIn('name="first_name"', form.text)
        self._assert_no_store(form)
        # 4. sign in -> PRG -> result -> auto-return targets /clinic/kiosk
        csrf = self._csrf_from(form.text)
        resp = self.url_open('/clinic/kiosk/signin', data={
            'csrf_token': csrf, 'first_name': 'Kim', 'last_name': 'Device',
            'date_of_birth': '2001-02-03'})
        self.assertEqual(resp.history[0].status_code, 303)
        self.assertIn('done=ok', resp.url)
        self.assertIn('url=/clinic/kiosk', resp.text.replace('&#34;', '"'))
        self._assert_no_store(resp)
        # reloading the result URL writes nothing (PRG)
        rows = self.Attendance.search_count([('event_id', '=', self.clinic.id)])
        self.url_open(resp.url)
        self.assertEqual(
            self.Attendance.search_count([('event_id', '=', self.clinic.id)]), rows)
        # 5. binding expires -> pairing screen again, same device row
        count = self.Device.search_count([])
        device.sudo().write({
            'bound_until': fields.Datetime.now() - timedelta(seconds=1)})
        resp = self.url_open('/clinic/kiosk')
        self.assertNotIn('name="first_name"', resp.text)
        self.assertNotIn('KD Clinic Now', resp.text)
        self.assertEqual(self.Device.search_count([]), count, "no re-mint")
        self.assertEqual(self.url_open('/clinic/kiosk/poll').json(), {'bound': False})
        # 6. revoked -> the next load mints a FRESH identity + new cookie
        old_raw = self._cookie_value()
        device._revoke()
        resp = self.url_open('/clinic/kiosk')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.Device.search_count([]), count + 1)
        self.assertIn(KIOSK_COOKIE + '=', resp.headers.get('Set-Cookie', ''),
                      "Set-Cookie overwrites the dead cookie")
        self.assertNotEqual(self._cookie_value(), old_raw)

    def test_poll_never_mints(self):
        self._clear_kiosk_cookie()
        before = self.Device.search_count([])
        poll = self.url_open('/clinic/kiosk/poll')
        self.assertEqual(poll.json(), {'bound': False})
        self.assertEqual(self.Device.search_count([]), before)

    def test_old_token_routes_are_gone(self):
        self.assertEqual(self.url_open('/clinic/kiosk/some-token').status_code, 404)
        resp = self.url_open('/clinic/kiosk/some-token/signin',
                             data={'first_name': 'x'})
        self.assertEqual(resp.status_code, 404)

    # ==================================================================
    # RATE LIMIT: DEVICE MINTING PER IP
    # ==================================================================
    def test_mint_rate_limit_by_ip(self):
        before = self.Device.search_count([])
        for _i in range(20):
            self._clear_kiosk_cookie()
            self.assertEqual(self.url_open('/clinic/kiosk').status_code, 200)
        self.assertEqual(self.Device.search_count([]), before + 20)
        # the 21st fresh device within the minute is refused: the ONE
        # inactive page, no row
        self._clear_kiosk_cookie()
        resp = self.url_open('/clinic/kiosk')
        self.assertEqual(resp.status_code, 404)
        self.assertIn('Borne inactive', resp.text)
        self._assert_no_store(resp)
        self.assertEqual(self.Device.search_count([]), before + 20)
        # a device that already HAS its cookie is not affected
        kiosk_mint_limiter.reset()
        _resp, _device = self._mint()
        for _i in range(25):
            self.assertEqual(self.url_open('/clinic/kiosk').status_code, 200)

    # ==================================================================
    # FORCED FRENCH + EN TOGGLE
    # ==================================================================
    def test_kiosk_is_french_whatever_the_browser_says(self):
        """No frontend_lang cookie, an ENGLISH Accept-Language — and the
        kiosk is French anyway: that is the feature (#1418 documented the
        old leak)."""
        english_browser = {'Accept-Language': 'en-US,en;q=0.9'}
        resp, device = self._mint()
        resp = self.url_open('/clinic/kiosk', headers=english_browser)
        self.assertIn('Demandez à votre thérapeute', resp.text)
        self.assertIn('lang="fr_CA"', resp.text)
        self.Device._pair(device._current_pairing_code(), self.clinic)
        resp = self.url_open('/clinic/kiosk', headers=english_browser)
        self.assertIn('Prénom', resp.text)
        self.assertIn('Je suis arrivé(e)', resp.text)
        self.assertIn('Politique de confidentialité', resp.text)
        self.assertNotIn('First name', resp.text)
        # sign-in flow stays French through the PRG
        csrf = self._csrf_from(resp.text)
        resp = self.url_open('/clinic/kiosk/signin', headers=english_browser, data={
            'csrf_token': csrf, 'first_name': 'Kim', 'last_name': 'Device',
            'date_of_birth': '2001-02-03'})
        self.assertIn('done=ok', resp.url)
        self.assertIn('Bienvenue', resp.text)

    def test_kiosk_url_is_never_lang_prefixed(self):
        """The kiosk routes are multilang=False: the website layer must
        never 303 /clinic/kiosk to /<lang>/clinic/kiosk. The device cookie
        is scoped Path=/clinic/kiosk, so a lang-prefixed URL arrives
        cookie-less and the kiosk re-mints a device on every load (found on
        the 1433 UAT with an English browser bounced to /en/clinic/kiosk).
        Meaningful on a website-installed DB (the project CI, staging); a
        websiteless run has no multilang routing and passes trivially."""
        website = self.env['ir.module.module']._get('website')
        if website.state == 'installed':
            # a second ACTIVE website language is what triggers the
            # lang-prefix redirect for a matching Accept-Language
            self.env['res.lang']._activate_lang('fr_CA')
            fr = self.env['res.lang']._lang_get('fr_CA')
            for site in self.env['website'].search([]):
                site.language_ids = [Command.link(fr.id)]
        self._clear_kiosk_cookie()
        for accept in ('fr-CA,fr;q=0.9', 'en-US,en;q=0.9'):
            resp = self.url_open('/clinic/kiosk', allow_redirects=False,
                                 headers={'Accept-Language': accept})
            self.assertEqual(resp.status_code, 200,
                             "kiosk must serve directly, never redirect "
                             "to a lang-prefixed URL (got %s for %s)"
                             % (resp.status_code, accept))
            self.assertNotIn('Location', resp.headers)
        # the device cookie earned on the FIRST hit must come back on the
        # next one — no re-mint churn
        count_before = self.Device.search_count([])
        self.url_open('/clinic/kiosk')
        self.assertEqual(self.Device.search_count([]), count_before)

    def test_english_toggle_is_per_request_and_resets(self):
        device = self._bind()
        # the French form offers « English », pointing at ?lang=en
        resp = self.url_open('/clinic/kiosk')
        self.assertIn('/clinic/kiosk?lang=en', resp.text)
        # ?lang=en flips this request
        resp = self.url_open('/clinic/kiosk?lang=en')
        self.assertIn('First name', resp.text)
        self.assertIn('I have arrived', resp.text)
        self.assertNotIn('Prénom', resp.text)
        self.assertIn('lang="en_US"', resp.text)
        # the hidden input carries it through the POST...
        self.assertIn('name="lang" value="en"', resp.text)
        csrf = self._csrf_from(resp.text)
        resp = self.url_open('/clinic/kiosk/signin', data={
            'csrf_token': csrf, 'first_name': 'Kim', 'last_name': 'Device',
            'date_of_birth': '2001-02-03', 'lang': 'en'})
        self.assertIn('done=ok', resp.url)
        self.assertIn('lang=en', resp.url)
        self.assertIn('Welcome!', resp.text)
        # ...but the auto-return target is the bare dispatcher: French again
        self.assertIn('url=/clinic/kiosk', resp.text.replace('&#34;', '"'))
        resp = self.url_open('/clinic/kiosk')
        self.assertIn('Prénom', resp.text)
        self.assertTrue(device._is_bound())

    # ==================================================================
    # SURFACE HYGIENE
    # ==================================================================
    def test_no_off_domain_links_or_web_storage_on_any_screen(self):
        device = self._bind()
        pages = []
        # pairing
        device._unbind()
        pages.append(self.url_open('/clinic/kiosk'))
        # form + result
        self.Device._pair(device._current_pairing_code(), self.clinic)
        pages.append(self.url_open('/clinic/kiosk'))
        pages.append(self.url_open('/clinic/kiosk?done=ok'))
        for resp in pages:
            self._assert_no_store(resp)
            self.assertFalse(re.search(r'(href|src|action)="https?://', resp.text),
                             "no off-domain resource on the kiosk surface")
            self.assertNotIn('localStorage', resp.text)
            self.assertNotIn('sessionStorage', resp.text)
            self.assertIn('pageshow', resp.text, "bfcache guard on every screen")

    def test_idle_seconds_setting_reaches_the_form(self):
        self._bind()
        self.env['ir.config_parameter'].sudo().set_param(IDLE_PARAM, '33')
        resp = self.url_open('/clinic/kiosk')
        self.assertIn('data-idle-seconds="33"', resp.text)
        self.assertIn('33; url=/clinic/kiosk', resp.text.replace('&#34;', '"'),
                      "noscript fallback at the same value")
        self.env['ir.config_parameter'].sudo().set_param(IDLE_PARAM, 'garbage')
        resp = self.url_open('/clinic/kiosk')
        self.assertIn('data-idle-seconds="75"', resp.text, "default survives garbage")

    # ==================================================================
    # PURGE CRON + ACL
    # ==================================================================
    def test_purge_cron_drops_only_never_paired_old_rows(self):
        _r, fresh_unpaired = self._mint()
        _r, old_unpaired = self._mint()
        old_paired = self._bind()
        stale = fields.Datetime.now() - timedelta(hours=25)
        self.env.cr.execute(
            "UPDATE sports_clinic_kiosk_device SET create_date = %s WHERE id IN %s",
            (stale, (old_unpaired.id, old_paired.id)))
        self.Device.invalidate_model()
        self.Device._cron_purge_unpaired_devices()
        self.assertTrue(fresh_unpaired.exists(), "younger than 24h: kept")
        self.assertFalse(old_unpaired.exists(), "never paired + old: purged")
        self.assertTrue(old_paired.exists(), "paired devices are never purged")

    def test_device_model_is_system_only(self):
        device = self._bind()
        with self.assertRaises(AccessError), mute_logger('odoo.addons.base.models.ir_rule', 'odoo.addons.base.models.ir_model'):
            self.Device.with_user(self.tp).search([])
        with self.assertRaises(AccessError), mute_logger('odoo.addons.base.models.ir_rule', 'odoo.addons.base.models.ir_model'):
            device.with_user(self.tp).read(['token_hash'])
