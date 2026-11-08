"""Portal app shell — the clinic's pages (task 1579, epic #1535; the engine
moved to ``bemade_portal_kit``, task 5196: ``portal.kit.pk_resolve`` /
``pk_match_url`` / ``pk_safe_return_url``).

ONE place decides, for every app-shell page, where « back » goes, what the
context line under the title says and what the breadcrumb trail is. The page
templates never set them by hand.

Parent registry
---------------
``sc_pages()`` (below, registered by ``portal.kit._pk_pages`` in
``sc_app_roles.py``) lists each shell page (its QWeb template id, without
the module prefix) as a kit ``Page``:

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
honoured only when it is a same-site path (``pk_safe_return_url``) that matches
a registered page whose records the CURRENT user may read (``pk_match_url``); it
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
from urllib.parse import quote, urlencode

from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import (
    Page, pk_arg, pk_int, pk_readable, pk_safe_return_url, pk_static_page)

_lt = LazyTranslate(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    clinic = pk_readable(env, 'sports.event', raw)
    if clinic and clinic.sudo().event_type != 'clinic':
        return None
    return clinic


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


def _team_from(env, match, args):
    team = pk_readable(env, 'sports.team', pk_arg(args, 'team_id'))
    return {'team': team} if team else None


def _player_from(env, match, args):
    player = pk_readable(env, 'sports.patient', pk_arg(args, 'player_id'))
    if not player:
        return None
    team = pk_readable(env, 'sports.team', pk_arg(args, 'team_id'))
    if team and team not in player.sudo().team_ids:
        team = None
    return {'player': player, 'team': team,
            'clinic_event': _clinic_from(env, pk_arg(args, 'clinic_id'))}


def _player_url(v):
    return '/my/player?player_id=%s%s' % (_player_of(v).id, _ctx_qs(v))


def _player_page_parent(v):
    if v.get('team'):
        return ('sc_app_team', {'team': v['team'], 'tab': 'players'})
    if v.get('clinic_event'):
        return ('sc_app_clinic', {'event': v['clinic_event']})
    return ('sc_app_players', {})


def _player_context(v, players_label):
    """« Team · position » under « #12 Last, First » (owner review 2026-10-10;
    an Identity save updates it in place)."""
    team = v.get('sc_player_team')
    team_label = team.name if team else str(players_label)
    player = _player_of(v)
    return ' · '.join(part for part in (team_label, player.position if player else '') if part)


def _clinic_from_path(env, match, args):
    clinic = _clinic_from(env, match.group(1))
    return {'event': clinic} if clinic else None


def _event_from(env, match, args):
    event = pk_readable(env, 'sports.event', match.group(1))
    return {'event': event} if event else None


def _activity_from(env, match, args):
    activity = pk_readable(env, 'mail.activity', match.group(1))
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
    return pk_safe_return_url(value, None)


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
        team = record.env['sports.team'].browse(pk_int(v.get('team_id')) or [])
        return ('sc_app_player', {'player': record, 'team': team or None,
                                  'clinic_event': v.get('clinic_event') or None})
    if record and v.get('model') == 'sports.team':
        return ('sc_app_team', {'team': record})
    if record and v.get('model') == 'sports.event':
        return ('sc_app_event', {'event': record})
    return ('sc_app_activities', {})


def _digest_history_from(env, match, args):
    team = pk_readable(env, 'sports.team', match.group(1))
    return {'team': team} if team else None


# Pages rendered with the shell layout that are top level on purpose (the
# rest MUST declare a parent — tests/test_app_shell_nav_1579.py).
TOP_LEVEL = frozenset({
    'sc_app_home', 'sc_app_teams', 'sc_app_players', 'sc_app_clinics',
    'sc_app_more', 'sc_app_notepad', 'sc_app_activities',
})


def sc_pages(kit):
    """The clinic's shell pages, registered by ``portal.kit._pk_pages``
    (``models/sc_app_roles.py``). ``kit`` is the ``portal.kit`` model (its
    nav labels name the top-level pages)."""
    label = kit.pk_nav_label
    players_label = label('players')
    return [
        # -- top level (logo, no back) -------------------------------------
        pk_static_page('sc_app_home', '/my/home', _lt('Dashboard')),  # owner 2026-10-18 (#1623)
        pk_static_page('sc_app_teams', '/my/teams', label('teams')),
        pk_static_page('sc_app_players', '/my/players', label('players')),
        pk_static_page('sc_app_clinics', '/my/clinics', label('clinic')),
        pk_static_page('sc_app_more', '/my/app/more', label('more')),
        # Owner review 2026-10-10 made « Notepad » a phone tab: a top-level page.
        pk_static_page('sc_app_notepad', '/my/notepad', label('notepad')),
        Page('sc_app_activities', url='/my/activities', label=label('activities'),
             path=r'/my/activities', parent=_activities_parent,
             context=lambda v: v.get('sc_context_title') or None,
             return_url=lambda v: v.get('sc_clock_from')),
        # -- « Plus » pages ------------------------------------------------
        pk_static_page('sc_app_events', '/my/events', label('events'),
                       parent=lambda v: ('sc_app_more', {})),
        pk_static_page('sc_app_events_calendar', '/my/events/calendar', label('events'),
                       parent=lambda v: ('sc_app_more', {})),
        pk_static_page('sc_app_timesheets', '/my/sc/timesheets', label('timesheets'),
                       parent=lambda v: ('sc_app_more', {})),
        pk_static_page('sc_app_install', '/my/app/install', label('install'),
                       parent=lambda v: ('sc_app_more', {})),
        # Task 1606: « Paramètres », opened from the user menu (not a page of
        # « Plus »): a sub-page of the home — back = where the user came from
        # (sc_app_nav.js), else the home.
        pk_static_page('sc_app_settings', '/my/app/settings', _lt('Settings'),
                       parent=lambda v: ('sc_app_home', {})),
        # Task 1624: « Configurer » the dashboard — a sub-page of the home.
        pk_static_page('sc_app_dashboard_configure', '/my/app/dashboard/configure',
                       _lt('Configure the dashboard'), parent=lambda v: ('sc_app_home', {})),
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
             parent=_player_page_parent,
             context=lambda v: _player_context(v, players_label)),
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
    ]
