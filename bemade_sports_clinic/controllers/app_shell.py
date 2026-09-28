"""Portal app shell (task 1538, epic #1535) — P1a.

The new Fit Crew app shell renders ONLY when the system switch
``bemade_sports_clinic.app_shell_enabled`` is on (staging until the launch)
AND the user holds at least one app role (see ``models/sc_app_roles.py``).
With the switch off (prod) every page renders exactly today's template.

Every migrated page picks its template through ONE helper,
``AppShellMixin._sc_render(legacy_template, app_template, values)``, so
flipping the switch — or removing the legacy path at P4 — is a one-line
change per page.

P1b (task 1542) adds:

* the server autosave pattern — ``POST /my/app/save/<model>/<id>`` driven by
  the declarative ``SAVE_REGISTRY`` (EMPTY in production code until P2: the
  tests register a test-only entry);
* the installable app — ``/my/app.webmanifest``, ``/my/service-worker.js``,
  the data-free ``/my/app/offline`` page and « Plus › Installer
  l'application » (``/my/app/install``). The manifest, the service worker
  and the offline page answer 404 while the switch is off: the page script
  (``sc_sw_register.js``) then unregisters any ``/my/`` registration a
  device still holds (the kill switch).
"""
import json
from datetime import timedelta

from markupsafe import Markup

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.modules.module import get_manifest
from odoo.tools import file_open, format_datetime

from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models import sc_app_roles
from .access_control_mixin import AccessControlMixin

APP_SHELL_PARAM = 'bemade_sports_clinic.app_shell_enabled'
# The ONLY fields /my/app/pref may write, with their allowed values.
PREF_FIELDS = {
    'sc_nav_mode': ('back', 'crumbs'),
    'sc_theme': ('dark', 'light'),
}
# ---------------------------------------------------------------------------
# Server autosave (task 1542) — WHAT may be saved field by field.
#
#   SAVE_REGISTRY = {
#       '<model>': {
#           'fields': ('field_a', 'field_b'),        # the allowlist
#           'check': callable(controller, record),   # raises AccessError /
#                                                    # MissingError to refuse;
#                                                    # reuse AccessControlMixin
#       },
#   }
#
# Empty on purpose until P2 (the injury form, where autosave is private to the
# author). The write itself runs AS THE USER (no sudo): ACLs, record rules and
# the models' own write guards still apply on top of ``check``.
# ---------------------------------------------------------------------------
SAVE_REGISTRY = {}

# PWA (task 1542): static files the service worker precaches, besides the
# offline page. Never a /my/ page or any data.
SW_PRECACHE_STATIC = (
    '/bemade_sports_clinic/static/src/css/sc_offline.css',
    '/bemade_sports_clinic/static/src/img/sc_logo_chrome.png',
    '/bemade_sports_clinic/static/src/img/sc_icon_192.png',
)
SW_SOURCE = 'bemade_sports_clinic/static/src/sw/sc_service_worker.js'
SC_MIDNIGHT = '#120e12'

HOME_TEAMS_LIMIT = 8
HOME_UPCOMING_LIMIT = 5
_TRUTHY = ('1', 'true', 'yes', 'on')


class AppShellMixin:
    """Switch + role gate + the shell's render values. Mixed into every
    CustomerPortal controller that serves a migrated page."""

    @staticmethod
    def _sc_app_shell_enabled():
        raw = request.env['ir.config_parameter'].sudo().get_param(APP_SHELL_PARAM)
        return str(raw or '').strip().lower() in _TRUTHY

    def _sc_app_shell_active(self):
        """Switch on AND the viewer holds an app role."""
        if not self._sc_app_shell_enabled():
            return False
        user = request.env.user
        if user._is_public():
            return False
        return bool(user._sc_app_roles() & sc_app_roles.APP_ROLES)

    def _sc_booking_enabled(self):
        """The bookings addon (appointment_portal_staff) flags its home card
        through ``_prepare_home_portal_values([])``; absent addon = False."""
        try:
            return bool(self._prepare_home_portal_values([]).get('booking_card_enable'))
        except AccessError:
            return False

    @staticmethod
    def _sc_nav_items(entries):
        """Registry entries -> render dicts with the labels translated in the
        request language."""
        items = []
        for entry in entries:
            item = dict(entry)
            item['label'] = str(entry['label'])
            item['subtitle'] = str(entry['subtitle']) if entry.get('subtitle') else ''
            items.append(item)
        return items

    def _sc_app_values(self, values):
        """``values`` + everything ``sc_app_layout`` needs."""
        user = request.env.user
        roles = user._sc_app_roles()
        ctx = {'booking_card_enable': self._sc_booking_enabled()}
        tabs = self._sc_nav_items(sc_app_roles.visible_nav(roles, 'tab', ctx))
        rail = self._sc_nav_items(sc_app_roles.visible_nav(roles, 'rail', ctx))
        plus = self._sc_nav_items(sc_app_roles.visible_nav(roles, 'plus', ctx))
        labels = {
            entry['key']: str(entry['label']) for entry in sc_app_roles.NAV_REGISTRY
        }
        path = request.httprequest.path
        query = request.httprequest.query_string.decode()
        initials = ''.join(part[:1] for part in (user.name or '').split()[:2]).upper()
        shell = {
            'sc_app_shell': True,
            'sc_roles': roles,
            'sc_can': lambda key: sc_app_roles.can(key, roles),
            'sc_tabs': tabs,
            'sc_rail': rail,
            'sc_plus': plus,
            'sc_nav_labels': labels,
            'sc_theme': user.sc_theme or 'dark',
            'sc_nav_mode': user.sc_nav_mode or 'back',
            'sc_current_url': path + ('?' + query if query else ''),
            'sc_search_url': '/my/players' if any(t['key'] == 'players' for t in rail) else False,
            'sc_user_initials': initials or '?',
            # Task 1542: the device draft store is namespaced by db + uid.
            'sc_db': request.db or '',
            'sc_uid': user.id,
            # Row builder for list templates (computed in the shell only, so
            # the legacy pages pay nothing for it).
            'sc_team_row': self._sc_team_row,
        }
        shell.update(values)
        return shell

    def _sc_render(self, legacy_template, app_template, values):
        """THE per-page switch: the app template in the shell, else today's."""
        if app_template and self._sc_app_shell_active():
            return request.render(app_template, self._sc_app_values(values))
        return request.render(legacy_template, values)

    # ------------------------------------------------------------------
    # Row builders shared by the home and the teams list
    # ------------------------------------------------------------------
    @staticmethod
    def _sc_singular(count):
        """French takes the singular for 0 and 1 (« 0 blessé »), English
        only for 1 — the module's other count labels use ``count == 1``."""
        lang = request.env.lang or ''
        return count == 1 or (count == 0 and lang.startswith('fr'))

    @staticmethod
    def _sc_team_row(team, with_org=False):
        no_play = team.stage_no_play_count or 0
        practice_ok = team.stage_practice_ok_count or 0
        if no_play:
            status = 'red'
        elif practice_ok:
            status = 'yellow'
        else:
            status = 'green'
        players = team.player_count or 0
        counts = ' · '.join((
            _("%s player", players) if AppShellMixin._sc_singular(players)
            else _("%s players", players),
            _("%s injured player", no_play) if AppShellMixin._sc_singular(no_play)
            else _("%s injured", no_play),
            _("%s returning", practice_ok),
        ))
        org = team.sudo().parent_id.name if with_org else ''
        return {
            'id': team.id,
            'title': team.name,
            'subtitle': ' · '.join(part for part in (org, counts) if part),
            'status': status,
            'url': '/my/team?team_id=%s' % team.id,
        }


class AppShellPortal(CustomerPortal, AccessControlMixin, AppShellMixin):

    # ------------------------------------------------------------------
    # /my/home — app home (« Équipes ») when the shell is active
    # ------------------------------------------------------------------
    @http.route()
    def home(self, **kw):
        if kw.get('classic') or not self._sc_app_shell_active():
            return super().home(**kw)
        values = self._prepare_portal_layout_values()
        values.update(self._sc_home_values())
        return request.render('bemade_sports_clinic.sc_app_home', self._sc_app_values(values))

    def _sc_home_values(self):
        env = request.env
        user = env.user
        roles = user._sc_app_roles()
        values = {'page_name': 'home'}
        teams = env['sports.team']
        # ACLs decide: a role the registry shows a section to may still lack
        # the model access (e.g. an internal user with only a staff row) —
        # skip the section's data rather than 403 the whole home.
        if sc_app_roles.can('home.team_status', roles) and teams.has_access('read'):
            role = 'tp' if roles & sc_app_roles.TP else 'coach'
            teams = teams.search(
                [('staff_ids.user_ids', '=', user.id)],
                order='last_player_activity_%s_at desc nulls last, name, id' % role)
            players = teams.patient_ids
            values.update({
                'sc_teams_count': len(teams),
                'sc_team_rows': [self._sc_team_row(team) for team in teams[:HOME_TEAMS_LIMIT]],
                'sc_stat_injured': len(players.filtered(lambda p: p.stage == 'no_play')),
                'sc_stat_returning': len(players.filtered(lambda p: p.stage == 'practice_ok')),
                'sc_stat_available': len(players.filtered(lambda p: p.stage == 'healthy')),
            })
        events_readable = env['sports.event'].has_access('read')
        if sc_app_roles.can('home.upcoming', roles) and events_readable:
            values['sc_upcoming'] = self._sc_upcoming_rows(teams)
        if sc_app_roles.can('home.clinic_teaser', roles) and events_readable:
            values['sc_clinics_today'] = self._sc_clinics_today_count()
        return values

    def _sc_clinics_today_count(self):
        """Today's clinics assigned to the viewer — the /my/clinics default
        filters (same window as ClinicPortal._clinic_time_domain('today')),
        for portal AND internal therapists."""
        user = request.env.user
        today = fields.Date.to_string(
            fields.Datetime.context_timestamp(user, fields.Datetime.now()).date())
        domain = self._prepare_events_domain('my') + [
            ('event_type', '=', 'clinic'),
            ('date_start', '>=', self._date_bound_to_utc(today, end_of_day=False)),
            ('date_start', '<=', self._date_bound_to_utc(today, end_of_day=True)),
        ]
        return request.env['sports.event'].search_count(domain)

    def _sc_upcoming_rows(self, teams):
        env = request.env
        user = env.user
        now = fields.Datetime.now()
        horizon = now + timedelta(days=env['sports.team']._dashboard_upcoming_events_days())
        domain = self._prepare_events_domain() + [
            ('date_start', '>=', now),
            ('date_start', '<=', horizon),
            '|', ('team_ids', 'in', teams.ids or [0]),
            ('assigned_staff_ids', 'in', [user.id]),
        ]
        events = env['sports.event'].search(domain, order='date_start, id',
                                            limit=HOME_UPCOMING_LIMIT)
        kinds = dict(env['sports.event']._fields['event_type']._description_selection(env))
        rows = []
        for event in events:
            rows.append({
                'when': format_datetime(env, event.date_start, tz=user.tz or env.context.get('tz'),
                                        dt_format='EEE d MMM · HH:mm'),
                'kind': kinds.get(event.event_type, ''),
                'name': event.name or '',
                'url': '/my/event/%s' % event.id,
            })
        return rows

    # ------------------------------------------------------------------
    # /my/app/more — « Plus »
    # ------------------------------------------------------------------
    @http.route(['/my/app/more'], type='http', auth='user', website=True)
    def sc_app_more(self, **kw):
        if not self._sc_app_shell_active():
            return request.redirect('/my/home')
        values = self._prepare_portal_layout_values()
        values['page_name'] = 'sc_app_more'
        return request.render('bemade_sports_clinic.sc_app_more', self._sc_app_values(values))

    # ------------------------------------------------------------------
    # /my/app/pref — the two self-service preferences, nothing else
    # ------------------------------------------------------------------
    @http.route(['/my/app/pref'], type='http', auth='user', website=True,
                methods=['POST'], multilang=False)
    def sc_app_pref(self, **post):
        """Set ``sc_nav_mode`` / ``sc_theme`` on the CALLER's own record.

        CSRF is enforced by the http POST route. Any other field, a bad value
        or another user's id is refused and nothing is written. A caller that
        accepts JSON (the app-bar toggle) gets JSON; a plain form post (no-JS
        path) is redirected back to ``redirect`` (same-site paths only)."""
        user = request.env.user
        post.pop('csrf_token', None)
        redirect = post.pop('redirect', None)
        target = post.pop('user_id', None)
        if target not in (None, '') and str(target) != str(user.id):
            return request.make_json_response({'error': 'forbidden'}, status=403)
        if not post or set(post) - set(PREF_FIELDS):
            return request.make_json_response({'error': 'bad_request'}, status=400)
        for name, value in post.items():
            if value not in PREF_FIELDS[name]:
                return request.make_json_response({'error': 'bad_request'}, status=400)
        user.write(dict(post))
        accept = request.httprequest.headers.get('Accept', '')
        if 'application/json' in accept:
            return request.make_json_response({
                'sc_nav_mode': user.sc_nav_mode,
                'sc_theme': user.sc_theme,
            })
        if not (redirect and redirect.startswith('/')
                and not redirect.startswith('//') and '\\' not in redirect):
            redirect = '/my/app/more'
        return request.redirect(redirect)

    # ------------------------------------------------------------------
    # /my/app/save/<model>/<id> — the server autosave pattern (task 1542)
    # ------------------------------------------------------------------
    @staticmethod
    def _sc_save_json(payload, status=200):
        return request.make_json_response(payload, status=status)

    @staticmethod
    def _sc_save_value(record, name):
        value = record[name]
        field = record._fields[name]
        if field.type in ('many2one',):
            return value.id or False
        if field.type in ('date', 'datetime'):
            return field.to_string(value) if value else False
        return value

    @http.route(['/my/app/save/<string:model>/<int:record_id>'], type='http', auth='user',
                methods=['POST'], csrf=True, multilang=False)
    def sc_app_save(self, model, record_id, field=None, value=None, write_date=None, **kw):
        """Save ONE field of ONE record, as the user.

        Body (form-encoded, CSRF enforced by the http POST route):
        ``field``, ``value``, ``write_date`` (the value the client last saw).
        Answers JSON:

        * 200 ``{ok, write_date}`` — saved;
        * 409 ``{conflict, current_value, current_write_date, by}`` — the
          record changed since ``write_date`` (nothing written);
        * 403 ``{error}`` — model / field outside ``SAVE_REGISTRY``, the
          registry check refused, or the ORM refused the write;
        * 400 ``{error}`` — missing parameters or an invalid value.
        """
        spec = SAVE_REGISTRY.get(model)
        if not spec or not field or field not in (spec.get('fields') or ()):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        if value is None or not write_date:
            return self._sc_save_json({'error': 'bad_request'}, 400)
        record = request.env[model].browse(record_id)
        try:
            if not record.exists():
                raise MissingError(_("Record not found."))
            spec['check'](self, record)
            current = fields.Datetime.to_string(record.write_date)
            if current != write_date:
                return self._sc_save_json({
                    'conflict': True,
                    'current_value': self._sc_save_value(record, field),
                    'current_write_date': current,
                    'by': record.sudo().write_uid.name or '',
                }, 409)
            if value == '' and record._fields[field].type not in ('char', 'text', 'html'):
                value = False
            record.write({field: value})
            record.invalidate_recordset(['write_date'])
            return self._sc_save_json({
                'ok': True,
                'write_date': fields.Datetime.to_string(record.write_date),
            })
        except (AccessError, MissingError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        except (UserError, ValidationError, ValueError) as exc:
            return self._sc_save_json({'error': 'invalid', 'message': str(exc)}, 400)

    # ------------------------------------------------------------------
    # PWA — manifest, service worker, offline page, install page (1542)
    # ------------------------------------------------------------------
    @http.route(['/my/app.webmanifest'], type='http', auth='public', methods=['GET'],
                multilang=False, sitemap=False)
    def sc_app_webmanifest(self, **kw):
        if not self._sc_app_shell_enabled():
            return request.not_found()
        img = '/bemade_sports_clinic/static/src/img/'
        labels = {entry['key']: str(entry['label']) for entry in sc_app_roles.NAV_REGISTRY}
        manifest = {
            'name': 'Le Fit Crew',
            'short_name': 'Fit Crew',
            'id': '/my/home',
            'start_url': '/my/home',
            'scope': '/my/',
            'display': 'standalone',
            'background_color': SC_MIDNIGHT,
            'theme_color': SC_MIDNIGHT,
            'icons': [
                {'src': img + 'sc_icon_192.png', 'sizes': '192x192', 'type': 'image/png',
                 'purpose': 'any'},
                {'src': img + 'sc_icon_512.png', 'sizes': '512x512', 'type': 'image/png',
                 'purpose': 'any'},
                {'src': img + 'sc_icon_maskable_512.png', 'sizes': '512x512',
                 'type': 'image/png', 'purpose': 'maskable'},
            ],
            'shortcuts': [
                {'name': labels['teams'], 'url': '/my/home'},
                {'name': labels['players'], 'url': '/my/players'},
            ],
        }
        return request.make_response(json.dumps(manifest), headers=[
            ('Content-Type', 'application/manifest+json'),
            ('Cache-Control', 'no-cache'),
        ])

    @staticmethod
    def _sc_sw_version():
        return get_manifest('bemade_sports_clinic').get('version') or '0'

    @http.route(['/my/service-worker.js'], type='http', auth='public', methods=['GET'],
                multilang=False, sitemap=False)
    def sc_app_service_worker(self, **kw):
        """The /my/-scoped service worker. ``no-cache`` so a device picks up a
        new version (or this route's 404, which the page script turns into an
        unregister) on its next visit."""
        if not self._sc_app_shell_enabled():
            return request.not_found()
        with file_open(SW_SOURCE) as source:
            body = source.read()
        body = (body
                .replace('__SC_SW_VERSION__', self._sc_sw_version())
                .replace('"__SC_SW_PRECACHE__"', json.dumps(list(SW_PRECACHE_STATIC))))
        return request.make_response(body, headers=[
            ('Content-Type', 'text/javascript; charset=utf-8'),
            ('Cache-Control', 'no-cache'),
            ('Service-Worker-Allowed', '/my/'),
        ])

    @http.route(['/my/app/offline'], type='http', auth='public', methods=['GET'],
                multilang=False, sitemap=False)
    def sc_app_offline(self, **kw):
        """Branded, DATA-FREE page the service worker shows when a navigation
        fails offline. Rendered without any layout: no user, no session info,
        no CSRF token — it is cached on the device."""
        if not self._sc_app_shell_enabled():
            return request.not_found()
        # The doctype is prepended here, not written in the template: a raw
        # text node at the template root changes how the view's terms are
        # extracted, and the page then rendered untranslated.
        html = request.env['ir.ui.view']._render_template(
            'bemade_sports_clinic.sc_app_offline', {})
        return request.make_response(
            Markup('<!DOCTYPE html>\n') + html,
            headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route(['/my/app/install'], type='http', auth='user', website=True,
                multilang=False)
    def sc_app_install(self, **kw):
        """« Plus › Installer l'application »: per-device steps. No banner
        anywhere else (owner decision 2026-09-27)."""
        if not self._sc_app_shell_active():
            return request.redirect('/my/home')
        values = self._prepare_portal_layout_values()
        values['page_name'] = 'sc_app_install'
        return request.render('bemade_sports_clinic.sc_app_install',
                              self._sc_app_values(values))
