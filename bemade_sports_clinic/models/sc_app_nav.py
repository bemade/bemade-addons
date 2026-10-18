"""Portal app shell — the navigation engine (task 1579, epic #1535).

ONE place decides, for every app-shell page, where « back » goes, what the
context line under the title says and what the breadcrumb trail is. The page
templates never set them by hand.

Parent registry
---------------
``PAGES`` maps each shell page (its QWeb template id, without the module
prefix) to a ``Page``:

* ``parent(v)``  -> ``(parent_key, parent_values)`` or ``None`` for a
  top-level page (logo instead of back). ``v`` is the page's render values
  (what the controller passes to ``_sc_render``); ``parent_values`` is the
  small dict the parent page's own resolvers need (e.g. ``{'team': team}``).
* ``url(v)``     the page's canonical URL (needed for every page that can be an
  ancestor).
* ``label(v)``   the page's crumb label: a static navigation label, or a
  record-derived one (team name, player « #12 Last, First », injury
  diagnosis, clinic name).
* ``context(v)`` optional: the context line under the title; default = the
  immediate parent's label.
* ``path`` + ``from_url(env, match, args)``: the page's URL pattern and how to
  rebuild its values from a URL. Together they are the ALLOWLIST of in-app
  return URLs (see below).
* ``return_url(v)``: optional; the page's « came from » URL (default
  ``v['return_url']``, else the request's ``?return_url=``).

Context via validated URL params
--------------------------------
A page with several legitimate parents (a player reached from a team, a
clinic or the players list) gets ``team_id`` / ``clinic_id`` (the controller
validates them and passes the records) or a ``return_url``. A return URL is
honoured only when it is a same-site path (``safe_return_url``) that matches a
registered page whose records the CURRENT user may read (``match_url``); it
then becomes the parent (back + last crumb, its query kept) and the trail is
that page's own. Anything else (external host, ``javascript:``, a non-shell
path, a record the user cannot read) is ignored: the declared parent wins.

Back = where you came from
--------------------------
The server always renders the RESOLVED parent as the back link's href (deep
link, shared link, fresh PWA launch, reload). In a browser,
``static/src/js/sc_app_nav.js`` keeps a per-tab stack of in-app page visits
and turns the back control into ``history.back()`` when the previous entry of
this tab is an in-app page.

Screen width decides
--------------------
Phones show the back chevron + context line, laptops the full trail (CSS
only, ``sc_components.scss``); there is no per-user setting.
"""
import re
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from odoo.exceptions import AccessError, MissingError
from odoo.tools.translate import LazyTranslate

from . import sc_app_roles

_lt = LazyTranslate(__name__)

# ---------------------------------------------------------------------------
# Return URL validation (ONE validator; the controllers' _safe_return_url,
# _local_return_url and the events' prefix checks all go through it).
# ---------------------------------------------------------------------------


def safe_return_url(value, fallback, prefixes=None):
    """``value`` if it is a same-site relative path, else ``fallback``
    (task 1544: no open redirect through a posted ``return_url``).

    Accepted: ``/…`` only. Refused: empty / non-string, a scheme
    (``https://…``, ``javascript:…``), protocol-relative ``//…``, any
    backslash (browsers read ``/\\evil`` as ``//evil``), and any control
    character (browsers drop tab/newline, so ``/<TAB>/evil`` would become
    ``//evil``). A plain space is allowed (search-filter return URLs).
    ``prefixes`` (optional tuple) further restricts the accepted paths
    (the events pages: their list and the home only)."""
    if not value or not isinstance(value, str):
        return fallback
    if (not value.startswith('/') or value.startswith('//')
            or '\\' in value
            or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in value)):
        return fallback
    if prefixes and not value.startswith(tuple(prefixes)):
        return fallback
    return value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def nav_label(key):
    """The (lazy) label of a NAV_REGISTRY entry."""
    for entry in sc_app_roles.NAV_REGISTRY:
        if entry['key'] == key:
            return entry['label']
    raise KeyError(key)


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _readable(env, model, raw_id):
    """``env[model]`` record ``raw_id`` if the CURRENT user may read it, else
    None (a return URL never reveals a record the user cannot open)."""
    rid = _int(raw_id)
    if not rid:
        return None
    record = env[model].browse(rid)
    try:
        if not record.exists():
            return None
        record.check_access('read')
    except (AccessError, MissingError):
        return None
    return record


def _arg(args, key):
    values = args.get(key) or []
    return values[0] if values else None


def _name(record, field='name'):
    return (record.sudo()[field] or '') if record else ''


def _ctx_qs(v):
    """``&team_id=…&clinic_id=…`` of a page's navigation context."""
    tail = ''
    team = v.get('team')
    clinic = v.get('clinic_event')
    if team:
        tail += '&team_id=%s' % team.id
    if clinic:
        tail += '&clinic_id=%s' % clinic.id
    return tail


def _player_of(v):
    return v.get('player') or v.get('patient') or (
        v['injury'].patient_id if v.get('injury') else None)


def _player_parent(v):
    """A player-scoped page's parent: the player page, same context."""
    return ('sc_app_player', {
        'player': _player_of(v),
        'team': v.get('team'),
        'clinic_event': v.get('clinic_event'),
    })


def _heading(v):
    player = _player_of(v)
    return player.sudo()._portal_heading_name() if player else ''


def _clinic_from(env, raw):
    clinic = _readable(env, 'sports.event', raw)
    if clinic and clinic.sudo().event_type != 'clinic':
        return None
    return clinic


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


class Page:
    __slots__ = ('key', 'parent', 'has_parent', 'url', 'label', 'context', 'path',
                 'from_url', 'return_url')

    def __init__(self, key, *, parent=None, url=None, label=None, context=None,
                 path=None, from_url=None, return_url=None):
        self.key = key
        self.has_parent = parent is not None
        self.parent = parent or (lambda v: None)
        self.url = url if callable(url) or url is None else (lambda v, _u=url: _u)
        self.label = label if callable(label) or label is None else (lambda v, _l=label: _l)
        self.context = context
        self.path = re.compile(path) if path else None
        self.from_url = from_url or (lambda env, match, args: {})
        self.return_url = return_url


def _static(key, url, label, parent=None, path=None):
    return Page(key, url=url, label=label, parent=parent,
                path=path or re.escape(url))


def _team_from(env, match, args):
    team = _readable(env, 'sports.team', _arg(args, 'team_id'))
    return {'team': team} if team else None


def _player_from(env, match, args):
    player = _readable(env, 'sports.patient', _arg(args, 'player_id'))
    if not player:
        return None
    team = _readable(env, 'sports.team', _arg(args, 'team_id'))
    if team and team not in player.sudo().team_ids:
        team = None
    return {'player': player, 'team': team,
            'clinic_event': _clinic_from(env, _arg(args, 'clinic_id'))}


def _player_url(v):
    return '/my/player?player_id=%s%s' % (_player_of(v).id, _ctx_qs(v))


def _player_page_parent(v):
    if v.get('team'):
        return ('sc_app_team', {'team': v['team'], 'tab': 'players'})
    if v.get('clinic_event'):
        return ('sc_app_clinic', {'event': v['clinic_event']})
    return ('sc_app_players', {})


def _player_context(v):
    """« Team · position » under « #12 Last, First » (owner review 2026-10-10;
    an Identity save updates it in place)."""
    team = v.get('sc_player_team')
    team_label = team.name if team else str(nav_label('players'))
    player = _player_of(v)
    return ' · '.join(part for part in (team_label, player.position if player else '') if part)


def _clinic_from_path(env, match, args):
    clinic = _clinic_from(env, match.group(1))
    return {'event': clinic} if clinic else None


def _event_from(env, match, args):
    event = _readable(env, 'sports.event', match.group(1))
    return {'event': event} if event else None


def _activity_from(env, match, args):
    activity = _readable(env, 'mail.activity', match.group(1))
    return _activity_values(activity) if activity else None


def _activity_values(activity):
    """The detail page's context records, from the activity itself."""
    values = {'activity': activity}
    model, res_id = activity.sudo().res_model, activity.sudo().res_id
    key = {'sports.patient': 'context_patient', 'sports.team': 'context_team',
           'sports.event': 'context_event'}.get(model)
    if key and res_id:
        values[key] = activity.env[model].browse(res_id)
    return values


def _activity_parent(v):
    if v.get('context_patient'):
        return ('sc_app_player', {'player': v['context_patient']})
    if v.get('context_team'):
        return ('sc_app_team', {'team': v['context_team']})
    if v.get('context_event'):
        return ('sc_app_event', {'event': v['context_event']})
    return ('sc_app_activities', {})


def _activities_parent(v):
    # The /my/team/activities and /my/event/activities wrappers (simplified).
    if v.get('simplified') and v.get('context_team'):
        return ('sc_app_team', {'team': v['context_team'], 'tab': 'activities'})
    if v.get('simplified') and v.get('context_event'):
        return ('sc_app_event', {'event': v['context_event']})
    # Task 1622: opened from the app bar clock — back to the page it was
    # tapped on (``sc_clock_from``, the page's return_url: resolve() honours
    # it when it is a readable registered page), else the home.
    if v.get('sc_clock_from'):
        return ('sc_app_home', {})
    return None


# Task 1622: the app bar clock (#1592) opens /my/activities from any shell
# page; its href carries that page (``sc_from``) so the activities page gets
# a way back. Only a safe same-site path is ever passed on; the activities
# page honours it only when it matches a registered page the user may read
# (resolve / match_url) — never an open redirect.
CLOCK_PATH = '/my/activities'
_CLOCK_DROPPED_ARGS = ('success', 'error')


def clock_origin(value):
    """The clock's origin ``sc_from`` if it is a safe same-site path."""
    return safe_return_url(value, None)


def clock_url(path, args):
    """The app bar clock's href on the page ``path`` (``args``: its query,
    a werkzeug MultiDict). On the activities page itself the clock keeps
    the origin the page was opened with (a page is never its own way back);
    the flash args (``success`` / ``error``) are not part of the origin."""
    if path == CLOCK_PATH:
        origin = clock_origin(args.get('sc_from'))
    else:
        query = urlencode([(key, value) for key, value in args.items(multi=True)
                           if key not in _CLOCK_DROPPED_ARGS])
        origin = clock_origin(path + ('?' + query if query else ''))
    url = CLOCK_PATH + '?sc_clock=1'
    return url + '&sc_from=' + quote(origin, safe='') if origin else url


def _activity_form_parent(v):
    """Edit: the activity. Create: the record it is for (its own page),
    else the activities list; a valid ``return_url`` wins (resolve)."""
    if v.get('activity'):
        return ('sc_app_activity_detail', _activity_values(v['activity']))
    record = v.get('record')
    if record and v.get('model') == 'sports.patient':
        team = record.env['sports.team'].browse(_int(v.get('team_id')) or [])
        return ('sc_app_player', {'player': record, 'team': team or None,
                                  'clinic_event': v.get('clinic_event') or None})
    if record and v.get('model') == 'sports.team':
        return ('sc_app_team', {'team': record})
    if record and v.get('model') == 'sports.event':
        return ('sc_app_event', {'event': record})
    return ('sc_app_activities', {})


def _digest_history_from(env, match, args):
    team = _readable(env, 'sports.team', match.group(1))
    return {'team': team} if team else None


PAGES = {page.key: page for page in (
    # -- top level (logo, no back) -------------------------------------
    _static('sc_app_home', '/my/home', _lt('Home')),
    _static('sc_app_teams', '/my/teams', nav_label('teams')),
    _static('sc_app_players', '/my/players', nav_label('players')),
    _static('sc_app_clinics', '/my/clinics', nav_label('clinic')),
    _static('sc_app_more', '/my/app/more', nav_label('more')),
    # Owner review 2026-10-10 made « Notepad » a phone tab: a top-level page.
    _static('sc_app_notepad', '/my/notepad', nav_label('notepad')),
    Page('sc_app_activities', url='/my/activities', label=nav_label('activities'),
         path=r'/my/activities', parent=_activities_parent,
         context=lambda v: v.get('sc_context_title') or None,
         return_url=lambda v: v.get('sc_clock_from')),
    # -- « Plus » pages ------------------------------------------------
    _static('sc_app_events', '/my/events', nav_label('events'),
            parent=lambda v: ('sc_app_more', {})),
    _static('sc_app_events_calendar', '/my/events/calendar', nav_label('events'),
            parent=lambda v: ('sc_app_more', {})),
    _static('sc_app_timesheets', '/my/sc/timesheets', nav_label('timesheets'),
            parent=lambda v: ('sc_app_more', {})),
    _static('sc_app_install', '/my/app/install', nav_label('install'),
            parent=lambda v: ('sc_app_more', {})),
    # Task 1606: « Paramètres », opened from the user menu (not a page of
    # « Plus »): a sub-page of the home — back = where the user came from
    # (sc_app_nav.js), else the home.
    _static('sc_app_settings', '/my/app/settings', _lt('Settings'),
            parent=lambda v: ('sc_app_home', {})),
    # Task 1620: the core « Mon compte » / « Sécurité » routes rendered in
    # the shell — sub-pages of « Paramètres ». No path on purpose: they are
    # never a return_url / « came from » target (test_app_shell_nav_1579).
    Page('sc_app_account', parent=lambda v: ('sc_app_settings', {})),
    Page('sc_app_security', parent=lambda v: ('sc_app_settings', {})),
    # -- teams ---------------------------------------------------------
    Page('sc_app_team', path=r'/my/team', from_url=_team_from,
         url=lambda v: '/my/team?team_id=%s%s' % (
             v['team'].id, '&tab=%s' % v['tab'] if v.get('tab') else ''),
         label=lambda v: _name(v['team']),
         parent=lambda v: ('sc_app_teams', {}),
         context=lambda v: v.get('sc_team_org') or None),
    Page('sc_app_team_digest_history', path=r'/my/team/(\d+)/digest-history',
         from_url=_digest_history_from,
         url=lambda v: '/my/team/%s/digest-history' % v['team'].id,
         label=_lt('Digest history'),
         parent=lambda v: ('sc_app_team', {'team': v['team']}),
         return_url=lambda v: v.get('back_url')),
    Page('sc_app_team_digest',
         parent=lambda v: ('sc_app_team_digest_history', {'team': v['team']}),
         context=lambda v: _name(v['team']),
         return_url=lambda v: None),
    # -- players -------------------------------------------------------
    Page('sc_app_player', path=r'/my/player', from_url=_player_from,
         url=_player_url, label=lambda v: _player_of(v).sudo()._portal_list_name(),
         parent=_player_page_parent, context=_player_context),
    Page('sc_app_player_create', parent=lambda v: ('sc_app_players', {})),
    # -- injuries ------------------------------------------------------
    Page('sc_app_injury_new', parent=_player_parent, context=_heading),
    # Task 1616: no injury page / injury documents page any more — the
    # injury is its open card (/my/injury/edit and /my/injury/documents
    # redirect there).
    Page('sc_app_treatment_notes', parent=_player_parent, context=_heading),
    # -- clinics -------------------------------------------------------
    Page('sc_app_clinic', path=r'/my/clinic/(\d+)', from_url=_clinic_from_path,
         url=lambda v: '/my/clinic/%s' % v['event'].id,
         label=lambda v: _name(v['event']),
         parent=lambda v: ('sc_app_clinics', {})),
    # -- events --------------------------------------------------------
    Page('sc_app_event', path=r'/my/event/(\d+)', from_url=_event_from,
         url=lambda v: '/my/event/%s' % v['event'].id,
         label=lambda v: _name(v['event']),
         parent=lambda v: ('sc_app_events', {})),
    Page('sc_app_event_form',
         parent=lambda v: ('sc_app_event', {'event': v['event']})
         if v.get('sc_form_mode') == 'edit' and v.get('event') else ('sc_app_events', {}),
         return_url=lambda v: None),
    # -- activities ----------------------------------------------------
    Page('sc_app_activity_detail', path=r'/my/activity/(\d+)', from_url=_activity_from,
         url=lambda v: '/my/activity/%s' % v['activity'].id,
         label=lambda v: (v['activity'].sudo().summary
                          or v['activity'].sudo().activity_type_id.name or ''),
         parent=_activity_parent,
         context=lambda v: v.get('related_record_name') or None,
         return_url=lambda v: None),
    Page('sc_app_activity_form', parent=_activity_form_parent,
         context=lambda v: v.get('record_name') or (
             v['activity'].sudo().res_name if v.get('activity') else '') or None,
         return_url=lambda v: None if v.get('activity') else v.get('return_url')),
)}

# Pages rendered with the shell layout that are top level on purpose (the
# rest MUST declare a parent — tests/test_app_shell_nav_1579.py).
TOP_LEVEL = frozenset({
    'sc_app_home', 'sc_app_teams', 'sc_app_players', 'sc_app_clinics',
    'sc_app_more', 'sc_app_notepad', 'sc_app_activities',
})


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


def _id_key(url):
    """A URL's identity: its path + the ``*id`` query args (the view state —
    tab, filters, flash messages — is not part of « which page »)."""
    parts = urlsplit(url or '')
    args = sorted((k, v) for k, vs in parse_qs(parts.query).items()
                  for v in vs if k.endswith('id'))
    return parts.path, tuple(args)


def match_url(env, url):
    """``(page_key, values)`` of the registered page ``url`` points to, if the
    URL is a safe in-app path whose records the current user may read."""
    url = safe_return_url(url, None)
    if not url:
        return None
    parts = urlsplit(url)
    args = parse_qs(parts.query)
    for page in PAGES.values():
        if not page.path or page.url is None:
            continue
        match = page.path.fullmatch(parts.path)
        if not match:
            continue
        values = page.from_url(env, match, args)
        if values is None:
            return None
        return page.key, values
    return None


def _label(page, values):
    return str(page.label(values)) if page.label else ''


def _trail(key, values):
    """[(label, url), …] from the top-level ancestor down to ``key``."""
    trail = []
    seen = set()
    while key and key not in seen:
        seen.add(key)
        page = PAGES[key]
        trail.insert(0, (_label(page, values), page.url(values)))
        parent = page.parent(values)
        key, values = parent if parent else (None, None)
    return trail


def resolve(key, values, env, request_url=None, request_return_url=None):
    """Navigation of page ``key`` rendered with ``values``.

    Returns ``{'parent_url', 'crumbs', 'context'}``: ``parent_url`` False on a
    top-level page; ``crumbs`` the ancestors, top first (the current page,
    the title, is appended by the layout); ``context`` the line under the
    title (shown with the back chevron)."""
    page = PAGES.get(key)
    if not page:
        return {'parent_url': False, 'crumbs': [], 'context': False}
    parent = page.parent(values)
    if parent is None:
        # Top level (logo): a return URL never adds a back chevron to a tab.
        return {'parent_url': False, 'crumbs': [],
                'context': str(page.context(values) or '') if page.context else False}
    if page.return_url is not None:
        raw_return = page.return_url(values)
    elif 'return_url' in values:
        raw_return = values.get('return_url')
    else:
        raw_return = request_return_url
    matched = match_url(env, raw_return) if raw_return else None
    if matched and request_url and _id_key(raw_return) == _id_key(request_url):
        matched = None  # a page is never its own parent
    if matched:
        crumbs = _trail(*matched)
        crumbs[-1] = (crumbs[-1][0], raw_return)
    else:
        crumbs = _trail(*parent)
    context = page.context(values) if page.context else None
    return {
        'parent_url': crumbs[-1][1],
        'crumbs': crumbs,
        'context': str(context) if context else crumbs[-1][0],
    }
