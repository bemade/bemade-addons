# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5200 (kit P5): the app's own pages and services.

* the switch: ``_pk_shell_active()`` (``portal.kit._pk_shell_active``);
* the shell's values: ``_pk_shell_values(values, page, extra)`` — what
  ``pk_app_layout`` reads (theme, preferences, languages, user menu, the
  navigation of the page registry, help, search, toast). It runs the
  language guard first. ``_pk_app_values(values, page)`` is the hook the
  kit's own pages call: a consumer's controller that inherits
  ``PortalKitShell`` overrides it to add its own values (and calls
  ``_pk_shell_values`` with them as ``extra``);
* the profile language guard (``_pk_profile_lang``, ``_pk_lang_url``,
  ``_pk_profile_lang_guard``, ``_pk_lang_options``): the user's profile
  language is the only source of truth;
* ``POST /my/app/pref``: the self-service preferences
  (``portal.kit._pk_pref_fields()``);
* ``/my`` and ``/my/home``: a user in an app is sent to the app's home
  (task 5392, ``portal.kit._pk_home_url()``);
* ``/my/app/settings`` (« Settings ») and ``/my/app/more`` (« More »);
* ``/my/account`` and ``/my/security`` rendered in the shell (the core
  routes keep their logic; only the rendering changes), with « My
  account »'s relaxed address rules and its phone rule
  (``portal.kit._pk_account_phone``);
* ``GET /my/app/search?q=``: the app bar's search
  (``portal.kit._pk_search_providers()``), an HTML fragment.

A consumer's portal controller inherits ``PortalKitShell`` (it then
precedes the kit in every route's class: its overrides win).
"""
import re
from types import MappingProxyType

import werkzeug.exceptions

from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request

from ..tools import (
    pk_contact_href, pk_display, pk_display_key, pk_draft_props, pk_field_props, pk_fold, pk_form_props,
    pk_fragment_key, pk_now_ms, pk_words,
)
from .pk_app import PortalKitApp

# Core template -> shell template.
PK_ACCOUNT_TEMPLATES = MappingProxyType({
    'portal.portal_my_details': 'bemade_portal_kit.pk_app_account',
    'portal.portal_my_security': 'bemade_portal_kit.pk_app_security',
})
# Where a successful « My account » save lands (the « saved » toast).
PK_ACCOUNT_SAVED_URL = '/my/account?pk_saved=1'
# The core headers these pages carry (no framing by other sites).
_KEPT_HEADERS = ('X-Frame-Options', 'Content-Security-Policy')
# « My account » in the app requires only these (the rest of the address is
# optional), on the routes the page uses; the stock portal pages and any
# checkout keep the core rules.
PK_ACCOUNT_REQUIRED_FIELDS = frozenset({'name', 'email'})
_RELAXED_PATHS = frozenset({'/my/account', '/my/address/submit'})
_RELAXED_PREFIX = '/my/address/country_info/'
_LANG_PREFIX = re.compile(r'^/[a-z]{2,3}(?:[_-][A-Za-z0-9@]{2,8})?(?=/my/)')
SEARCH_MIN = 2
SEARCH_LIMIT = 8


class PortalKitShell(PortalKitApp):

    # ------------------------------------------------------------------
    # The switch
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_shell_active():
        """The app's switch is on AND the viewer holds an app role."""
        return request.env['portal.kit']._pk_shell_active()

    # ------------------------------------------------------------------
    # The profile language is the only source of truth
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_profile_lang():
        """The frontend language serving the user's profile language
        (``res.users.lang``, or its nearest frontend sibling), or None when
        the frontend offers nothing close (the request's language stands)."""
        return request.env['ir.http'].get_nearest_lang(request.env.user.lang)

    @staticmethod
    def _pk_lang_url(url, lang_code):
        """``url`` (a local path + query) in ``lang_code``: any language
        prefix dropped, the prefix of ``lang_code`` added when it is not the
        default language and the path is a multilang route — the URL served
        in that language WITHOUT a further language redirect (no loop)."""
        env = request.env
        frontend = env['res.lang']._get_frontend()
        url_codes = [lang.url_code for lang in frontend.values()]
        path, sep, query = url.partition('?')
        parts = path.split('/')
        if len(parts) > 1 and parts[1] in url_codes:
            parts.pop(1)
        path = '/'.join(parts) or '/'
        lang = frontend.get(lang_code)
        default = env['ir.http']._get_default_lang()
        if (lang and lang.code != default.code and len(url_codes) > 1
                and env['ir.http']._is_multilang_url(path, url_codes)):
            path = '/%s%s' % (lang.url_code, path if path != '/' else '')
        return path + sep + query

    @classmethod
    def _pk_profile_lang_guard(cls):
        """A shell page served in another language than the user's profile
        one (a stale ``frontend_lang`` cookie, a language URL prefix) is
        redirected (GET / HEAD) to the same page in the profile language,
        the cookie reset to it. Other methods, and a page whose URL a
        language does not change (a ``multilang=False`` route: the redirect
        would point at itself, task 5389), are aligned in place. A public
        visitor is left alone.

        The cookie goes through ``request.future_response``: the frontend
        dispatch may already have queued the request's language there, and
        those headers are added after the response's own (the last one
        wins)."""
        user = request.env.user
        if user._is_public():
            return
        target = cls._pk_profile_lang()
        current = getattr(request, 'lang', None)
        if not target or not current or current.code == target:
            return
        request.future_response.set_cookie('frontend_lang', target)
        if request.httprequest.method in ('GET', 'HEAD'):
            query = request.httprequest.query_string.decode()
            here = request.httprequest.path + ('?' + query if query else '')
            url = cls._pk_lang_url(here, target)
            if url != here:
                werkzeug.exceptions.abort(request.redirect(url, code=303, local=True))
        request.lang = request.env['res.lang']._get_data(code=target)
        request.update_context(lang=target)

    @classmethod
    def _pk_lang_options(cls):
        """« Settings › Language »: one entry per frontend language, the
        profile language pressed; empty with a single language."""
        frontend = request.env['res.lang']._get_frontend()
        if len(frontend) < 2:
            return []
        current = cls._pk_profile_lang()
        shorts = [code.partition('_')[0] for code in frontend]
        options = []
        for code, lang in frontend.items():
            short = code.partition('_')[0]
            options.append({
                'code': code,
                # Two variants of one language (fr_CA + fr_FR): their names.
                'label': short.upper() if shorts.count(short) == 1 else lang.name,
                'name': lang.name,
                'active': code == current,
            })
        return options

    # ------------------------------------------------------------------
    # The shell's values
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_nav_items(entries):
        """Registry entries -> render dicts, the labels in the request
        language."""
        items = []
        for entry in entries:
            item = dict(entry)
            item['label'] = str(entry['label'])
            item['subtitle'] = str(entry['subtitle']) if entry.get('subtitle') else ''
            items.append(item)
        return items

    @staticmethod
    def _pk_search_values(app=None):
        """The app bar's search (``{'placeholder', 'href'}``), or False when
        no provider of the viewer's app is available to them."""
        kit = request.env['portal.kit']
        providers = kit.pk_search_providers(app)
        if not providers:
            return False
        return {
            'placeholder': str(kit._pk_search_placeholder()),
            'href': next((p['url'] for p in providers if p.get('url')), '#'),
        }

    def _pk_shell_values(self, values, page=None, extra=None):
        """``values`` + everything ``pk_app_layout`` reads. ``page`` is the
        page's template (``module.template``); its last part is the page
        key of the registry (back target, context line, crumbs) and of the
        help. ``extra``: a consumer's values (they replace the kit's, the
        page's ``values`` replace both); its ``pk_app_key`` (task 5391) names
        the app the page belongs to (default: the viewer's app)."""
        self._pk_profile_lang_guard()
        env = request.env
        kit = env['portal.kit']
        user = env.user
        page_key = (page or '').rpartition('.')[2]
        roles = user._pk_roles()
        # Task 5391: every lookup in one app: the consumer's (``extra``'s
        # ``pk_app_key``: its own pages), else the viewer's.
        app = (extra or {}).get('pk_app_key') or kit._pk_current_app()
        path = request.httprequest.path
        query = request.httprequest.query_string.decode()
        initials = ''.join(part[:1] for part in (user.name or '').split()[:2]).upper()
        shell = {
            'pk_app_shell': True,
            'pk_layout': kit._pk_layout(),
            'pk_theme': kit._pk_effective_theme(user),
            'pk_theme_choice': kit._pk_theme_choice_enabled(),
            'pk_pref_url': '/my/app/pref',
            'pk_theme_field': 'pk_theme',
            'pk_show_done': bool(user.sudo().pk_show_done_buttons),
            'pk_langs': self._pk_lang_options(),
            'pk_current_url': path + ('?' + query if query else ''),
            'pk_settings_url': '/my/app/settings',
            'pk_settings_active': page_key == 'pk_app_settings',
            'pk_user_initials': initials or '?',
            'pk_user_name': user.name or '',
            'pk_user_role': '',
            'pk_db': request.db or '',
            'pk_uid': user.id,
            'pk_rendered_at': pk_now_ms(),
            'pk_app_key': app or '',
            'pk_search': self._pk_search_values(app),
            'pk_notification': self._pk_pop_notification(),
            # The kit's render helpers (fragments, autosave field, read view).
            'pk_fragment_key': pk_fragment_key,
            'pk_field_props': pk_field_props,
            'pk_draft_props': pk_draft_props,
            'pk_form_props': pk_form_props,
            'pk_display': pk_display,
            'pk_display_key': pk_display_key,
            'pk_contact_href': pk_contact_href,
        }
        if not extra or 'pk_rail' not in extra:
            shell['pk_tabs'] = self._pk_nav_items(kit.pk_visible_nav(roles, 'tab', {}, app=app))
            shell['pk_rail'] = self._pk_nav_items(kit.pk_visible_nav(roles, 'rail', {}, app=app))
            shell['pk_plus'] = self._pk_nav_items(kit.pk_visible_nav(roles, 'plus', {}, app=app))
        shell.update(extra or {})
        shell.update(values)
        nav = kit.pk_resolve(
            page_key, shell,
            request_url=shell['pk_current_url'],
            request_return_url=request.httprequest.args.get('return_url'), app=app)
        shell.update({
            'pk_parent_url': nav['parent_url'],
            'pk_crumbs': nav['crumbs'],
            'pk_context': nav['context'],
            'pk_help': env['portal.kit.help'].pk_help_for(
                page_key, tab=request.params.get('tab') or shell.get('pk_help_tab')),
        })
        return shell

    def _pk_app_values(self, values, page=None):
        """The values of the kit's own pages: ``_pk_shell_values``. A
        consumer overrides this to add its values (``extra``)."""
        return self._pk_shell_values(values, page)

    def _pk_page(self, template, values):
        """A kit page in the shell (or its read fragments)."""
        values.setdefault('page_name', template.rpartition('.')[2])
        return self._pk_render(template, self._pk_app_values(values, template))

    # ------------------------------------------------------------------
    # /my, /my/home — the app's home (task 5392)
    # ------------------------------------------------------------------
    @http.route()
    def home(self, **kw):
        """A user in an app is sent to the app's home
        (``portal.kit._pk_home_url()``), in the request's language;
        ``?classic=1`` and everyone else get the portal home. The dashboard
        addon draws its own home here instead."""
        if not kw.get('classic'):
            url = request.env['portal.kit']._pk_home_url()
            if url:
                lang = getattr(request, 'lang', None)
                return request.redirect(self._pk_lang_url(url, lang.code) if lang else url)
        return super().home(**kw)

    # ------------------------------------------------------------------
    # /my/app/more — « More »; /my/app/settings — « Settings »
    # ------------------------------------------------------------------
    @http.route(['/my/app/more'], type='http', auth='user', website=True)
    def pk_app_more(self, **kw):
        if not self._pk_shell_active():
            return request.redirect('/my/home')
        return self._pk_page('bemade_portal_kit.pk_app_more', self._prepare_portal_layout_values())

    @http.route(['/my/app/settings'], type='http', auth='user', website=True)
    def pk_app_settings(self, **kw):
        if not self._pk_shell_active():
            return request.redirect('/my/home')
        return self._pk_page('bemade_portal_kit.pk_app_settings', self._prepare_portal_layout_values())

    # ------------------------------------------------------------------
    # /my/app/pref — the self-service preferences, nothing else
    # ------------------------------------------------------------------
    @http.route(['/my/app/pref'], type='http', auth='user', website=True,
                methods=['POST'], multilang=False)
    def pk_app_pref(self, **post):
        """Set preferences on the CALLER's own record: the fields of
        ``portal.kit._pk_pref_fields()`` with their allowed values, and/or
        ``lang`` (one of the frontend languages: the profile language,
        mirrored in the ``frontend_lang`` cookie and the session).

        CSRF is enforced by the http POST route. Any other field, a bad value
        or another user's id is refused and nothing is written. A caller that
        accepts JSON (the theme toggle) gets ``{pk_theme, lang}``; a plain
        form post is redirected back to ``redirect`` (same-site paths only)
        in the language chosen."""
        user = request.env.user
        allowed_fields = request.env['portal.kit']._pk_pref_fields()
        post.pop('csrf_token', None)
        redirect = post.pop('redirect', None)
        target = post.pop('user_id', None)
        if target not in (None, '') and str(target) != str(user.id):
            return request.make_json_response({'error': 'forbidden'}, status=403)
        if not post or set(post) - set(allowed_fields):
            return request.make_json_response({'error': 'bad_request'}, status=400)
        for name, value in post.items():
            allowed = allowed_fields[name]
            if allowed is None:
                allowed = request.env['res.lang']._get_frontend()
            if not value or value not in allowed:
                return request.make_json_response({'error': 'bad_request'}, status=400)
        vals = dict(post)
        for name in vals:
            field = user._fields.get(name)
            if field is not None and field.type == 'boolean':
                vals[name] = vals[name] == '1'
        user.write(vals)
        lang = post.get('lang')
        if lang:
            # The session context too (the backend and the http_routing
            # fallback read it); the cookie below wins anyway.
            request.session.context = dict(request.session.context, lang=lang)
        if 'application/json' in request.httprequest.headers.get('Accept', ''):
            response = request.make_json_response({
                'pk_theme': request.env['portal.kit']._pk_effective_theme(user),
                'lang': user.lang,
            })
        else:
            url = self._pk_safe_url(redirect, '/my/app/settings')
            if lang:
                url = self._pk_lang_url(url, lang)
            response = request.redirect(url)
        if lang:
            response.set_cookie('frontend_lang', lang)
        return response

    # ------------------------------------------------------------------
    # /my/app/notify-pref — the caller's notification preferences (1.17)
    # ------------------------------------------------------------------
    @http.route(['/my/app/notify-pref'], type='http', auth='user', website=True,
                methods=['POST'], multilang=False)
    def pk_app_notify_pref(self, kind=None, mode=None, redirect=None, push=None, **post):
        """Task 5516 (kit 1.17): store the CALLER's mode for notification
        kind ``kind`` (one of ``portal.kit.pk_notification_kinds()`` of the
        current app, a mode it allows). Anything else answers 400 and
        writes nothing. A JSON caller gets ``{kind, mode}``; a plain form
        post is redirected to ``redirect`` (same-site; default: the
        settings' « Notifications » section). CSRF: the http POST route.

        Task 5546 (kit 1.18): ``push`` (``'1'`` / ``'0'``) sets the kind's
        phone switch instead of (or with) the mode: only for a kind that
        declares ``push`` while ``portal.kit._pk_push_available()``. The
        JSON answer then also holds ``push``."""
        user = request.env.user
        kit = request.env['portal.kit']
        spec = next((k for k in kit.pk_notification_kinds() if k['key'] == kind), None)
        if not spec or (mode is None and push is None):
            return request.make_json_response({'error': 'bad_request'}, status=400)
        if mode is not None and mode not in spec['modes']:
            return request.make_json_response({'error': 'bad_request'}, status=400)
        if push is not None and (push not in ('0', '1') or not spec.get('push') or not kit._pk_push_available()):
            return request.make_json_response({'error': 'bad_request'}, status=400)
        Pref = request.env['portal.kit.notification.pref']
        pref = Pref.search([('user_id', '=', user.id), ('kind', '=', kind)], limit=1)
        vals = {}
        if mode is not None:
            vals['mode'] = mode
        if push is not None:
            vals['push'] = push == '1'
        if pref:
            pref.write(vals)
        else:
            Pref.create(dict(vals, user_id=user.id, kind=kind))
        if 'application/json' in request.httprequest.headers.get('Accept', ''):
            answer = {'kind': kind, 'mode': user._pk_notification_mode(kind)}
            if push is not None:
                answer['push'] = push == '1'
            return request.make_json_response(answer)
        return request.redirect(self._pk_safe_url(redirect, '/my/app/settings#pk_notifications'), code=303)

    @staticmethod
    def _pk_safe_url(value, fallback):
        return request.env['portal.kit'].pk_safe_return_url(value, fallback)

    # ------------------------------------------------------------------
    # /my/app/search — the app bar's search
    # ------------------------------------------------------------------
    @http.route('/my/app/search', type='http', auth='user', methods=['GET'], multilang=False, sitemap=False)
    def pk_app_search(self, q='', **kw):
        """The search sheet's body for ``q``: one group per provider (its
        near matches in a « Close results » group right after it), at most
        ``SEARCH_LIMIT`` rows each; « Type at least 2 letters » below
        ``SEARCH_MIN`` letters. Never cached."""
        query = (q or '').strip()
        words = pk_words(query)
        too_short = len(pk_fold(query).replace(' ', '')) < SEARCH_MIN
        groups = []
        if self._pk_shell_active() and not too_short and words:
            for provider in request.env['portal.kit'].pk_search_providers():
                rows = list(provider['search'](words, SEARCH_LIMIT, self) or [])
                exact = [row for row in rows if not row.get('near')][:SEARCH_LIMIT]
                near = [row for row in rows if row.get('near')][:SEARCH_LIMIT]
                groups.append({'key': provider['key'], 'title': str(provider['title']), 'rows': exact})
                groups.append({'key': '%s_near' % provider['key'], 'title': _("Close results"), 'rows': near})
        html = request.env['ir.ui.view']._render_template('bemade_portal_kit.pk_search_results', {
            'pk_query': query,
            'pk_too_short': too_short,
            'pk_search_groups': [group for group in groups if group['rows']],
        })
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8'),
                                                    ('Cache-Control', 'no-store')])

    # ------------------------------------------------------------------
    # /my/account — « My account », /my/security — « Security »
    # ------------------------------------------------------------------
    def _pk_core_in_shell(self, response, extra=None):
        """``response`` (a core page) rendered in the shell with its own
        values, when the shell is active and the core rendered one of the
        templates above; anything else (redirect, other template) as is."""
        template = getattr(response, 'template', None)
        app_template = PK_ACCOUNT_TEMPLATES.get(template)
        if not app_template or not getattr(response, 'is_qweb', False):
            return response
        if not self._pk_shell_active():
            return response
        values = dict(response.qcontext or {})
        values.update(extra or {})
        values['page_name'] = app_template.rpartition('.')[2]
        shell = self._pk_render(app_template, self._pk_app_values(values, app_template))
        for header in _KEPT_HEADERS:
            if header in response.headers:
                shell.headers[header] = response.headers[header]
        return shell

    @http.route()
    def account(self, **kwargs):
        if not self._pk_shell_active():
            return super().account(**kwargs)
        saved = kwargs.pop('pk_saved', None)
        if not kwargs.get('redirect'):
            # Core default: back to /my. In the app: back here, with a toast.
            kwargs['redirect'] = PK_ACCOUNT_SAVED_URL
        extra = {}
        if saved:
            extra['pk_notification'] = {
                'message': _("Your details have been saved."),
                'title': '',
                'tone': 'success',
            }
        return self._pk_core_in_shell(super().account(**kwargs), extra)

    def _pk_relaxed_address(self):
        """True when « My account »'s relaxed rules apply: an app user on one
        of the routes the page uses (render, save, country info)."""
        if not request:
            return False
        path = _LANG_PREFIX.sub('', request.httprequest.path)
        if path not in _RELAXED_PATHS and not path.startswith(_RELAXED_PREFIX):
            return False
        return self._pk_shell_active()

    def _get_mandatory_billing_address_fields(self, country_sudo):
        if self._pk_relaxed_address():
            return set(PK_ACCOUNT_REQUIRED_FIELDS)
        return super()._get_mandatory_billing_address_fields(country_sudo)

    def _get_mandatory_delivery_address_fields(self, country_sudo):
        if self._pk_relaxed_address():
            return set(PK_ACCOUNT_REQUIRED_FIELDS)
        return super()._get_mandatory_delivery_address_fields(country_sudo)

    def _get_mandatory_address_fields(self, country_sudo):
        # The core also requires the WHOLE address as soon as one part of it
        # is given: not in the app (a city alone is fine).
        if self._pk_relaxed_address():
            return set()
        return super()._get_mandatory_address_fields(country_sudo)

    def _validate_address_values(self, address_values, partner_sudo, *args, **kwargs):
        """« My account »'s phone follows ``portal.kit._pk_account_phone``
        (formatted, or refused with its message). In the controller only:
        res.partner keeps the core behaviour everywhere else."""
        invalid_fields, missing_fields, error_messages = super()._validate_address_values(
            address_values, partner_sudo, *args, **kwargs)
        if self._pk_relaxed_address() and address_values.get('phone'):
            country = request.env['res.country'].browse(
                int(address_values['country_id'])) if address_values.get('country_id') else None
            try:
                address_values['phone'] = request.env['portal.kit']._pk_account_phone(
                    address_values['phone'], country=country or None)
            except ValidationError as e:
                invalid_fields.add('phone')
                error_messages.append(e.args[0])
        return invalid_fields, missing_fields, error_messages

    @http.route()
    def security(self, **post):
        response = super().security(**post)
        return self._pk_core_in_shell(response, self._pk_security_extra())

    @http.route()
    def deactivate_account(self, validation, password, **post):
        response = super().deactivate_account(validation, password, **post)
        return self._pk_core_in_shell(response, self._pk_security_extra())

    @staticmethod
    def _pk_security_extra():
        """What the page shows, decided like the core does: the two-factor
        section only when ``auth_totp_portal`` adds it, the delete-account
        block for portal users only."""
        env = request.env
        return {
            'pk_totp_portal': bool(env.ref('auth_totp_portal.totp_portal_hook', raise_if_not_found=False)),
            'pk_can_deactivate': env.user.has_group('base.group_portal'),
        }
