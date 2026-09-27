"""Portal app shell — roles and declarative registries (task 1538, epic #1535).

How the new portal decides WHAT TO SHOW. Read this before adding a screen, a
menu entry, a field or a role.

Roles
-----
A user holds a SET of roles (``res.users._sc_app_roles()`` -> frozenset). One
person may hold several — a coach who is also a therapist, later a coach who
is also a parent. A role is resolved from:

* ``ROLE_GROUPS``      role -> group xmlids (any-of), and/or
* ``ROLE_STAFF_ROLES`` role -> ``sports.team.staff.role`` values (any-of) the
  user's partner holds on any team.

Active today: coach, head_coach, therapist, head_therapist, doctor,
clinic_admin, internal. RESERVED (declared, mapped to nothing yet): teacher,
parent, player, secretary. **Adding a future role = give it a group mapping in
``ROLE_GROUPS`` + mention it in the registry entries that concern it. No
template edit.** ``internal`` alone does not put a user in the app shell
(``APP_ROLES``): an internal user without any clinic role keeps the stock
portal.

Visibility rule (every registry below)
--------------------------------------
``include`` (any-of) and ``exclude`` (none-of). An entry is visible when the
user's roles intersect ``include`` AND do not intersect ``exclude`` — exclude
WINS: an entry excluded for ``coach`` stays hidden for a coach who is also a
therapist.

Registries
----------
* ``NAV_REGISTRY``: app navigation. ``placement`` says where an entry appears
  — ``tab`` (phone bottom bar), ``rail`` (laptop left rail), ``plus`` (the
  « Plus » page). ``requires`` is an optional callable(ctx) -> bool for
  feature gates (e.g. the bookings addon). Templates render
  ``visible_nav(roles, placement, ctx)`` and never branch on groups.
* ``VISIBILITY_REGISTRY``: fields and page sections, asked from QWeb with
  ``sc_can('patient.allergies')``. A key that names ``model`` + ``field`` is a
  field key: whatever it hides from a role MUST already be unreadable for that
  role server-side (field ``groups=`` / ACL / record rule) — the tests assert
  it. **The registry decides what is SHOWN, never what is ALLOWED**; security
  stays in ACLs and record rules.
"""
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
ACTIVE_ROLES = (
    'coach', 'head_coach', 'therapist', 'head_therapist', 'doctor',
    'clinic_admin', 'internal',
)
RESERVED_ROLES = ('teacher', 'parent', 'player', 'secretary')
ALL_ROLES = ACTIVE_ROLES + RESERVED_ROLES

_TP_GROUPS = (
    'bemade_sports_clinic.group_portal_treatment_professional',
    'bemade_sports_clinic.group_sports_clinic_treatment_professional',
)

ROLE_GROUPS = {
    'coach': ('bemade_sports_clinic.group_portal_team_coach',),
    'therapist': _TP_GROUPS,
    'clinic_admin': ('bemade_sports_clinic.group_sports_clinic_admin',),
    'internal': ('base.group_user',),
    # Reserved: no group yet. A later task only fills the tuple.
    'teacher': (),
    'parent': (),
    'player': (),
    'secretary': (),
}

ROLE_STAFF_ROLES = {
    'head_coach': ('head_coach',),
    'head_therapist': ('head_therapist',),
    'doctor': ('doctor',),
}

# Roles that put a user in the app shell (everything but ``internal``).
APP_ROLES = frozenset(role for role in ALL_ROLES if role != 'internal')

# Shorthands for the registries below.
STAFF = frozenset({'coach', 'head_coach', 'therapist', 'head_therapist',
                   'doctor', 'clinic_admin'})
TP = frozenset({'therapist', 'head_therapist', 'doctor', 'clinic_admin'})
EVERYONE = APP_ROLES


def _nav(key, label, icon, url, include, sequence, placement,
         exclude=(), requires=None, subtitle=None):
    return {
        'key': key, 'label': label, 'icon': icon, 'url': url,
        'include': frozenset(include), 'exclude': frozenset(exclude),
        'requires': requires, 'placement': tuple(placement),
        'sequence': sequence, 'subtitle': subtitle,
    }


# Placements (constants, not inline literals: babel's term extractor picks up
# stray string literals that follow an _lt() call in the same argument list).
TAB_RAIL = ('tab', 'rail')
RAIL_PLUS = ('rail', 'plus')
PLUS_ONLY = ('plus',)


def _bookings_enabled(ctx):
    return bool(ctx.get('booking_card_enable'))


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
NAV_REGISTRY = (
    # « Équipes » is the app home (/my/home); /my/teams is its full list.
    _nav('teams', _lt('Teams'), 'teams', '/my/home', STAFF, 10, TAB_RAIL),
    _nav('players', _lt('Players'), 'players', '/my/players', STAFF, 20, TAB_RAIL),
    _nav('clinic', _lt('Clinic'), 'clinic', '/my/clinics', TP, 30, TAB_RAIL),
    _nav('activities', _lt('Activities'), 'activities', '/my/activities', STAFF, 40,
         TAB_RAIL),
    _nav('bookings', _lt('Bookings'), 'bookings', '/my/bookings', EVERYONE, 50,
         RAIL_PLUS, requires=_bookings_enabled,
         subtitle=_lt('Your appointments')),
    _nav('more', _lt('More'), 'more', '/my/app/more', EVERYONE, 90, TAB_RAIL),
    # « Plus » only.
    _nav('events', _lt('Events and calendar'), 'calendar', '/my/events', STAFF, 110,
         PLUS_ONLY, subtitle=_lt('Games, practices, clinics')),
    _nav('notepad', _lt('Notepad'), 'note', '/my/notepad', TP, 120, PLUS_ONLY,
         subtitle=_lt('Your quick notes')),
    _nav('timesheets', _lt('Timesheets'), 'timesheet', '/my/sc/timesheets', TP, 130,
         PLUS_ONLY, subtitle=_lt('Event coverage')),
    _nav('digests', _lt('Daily summaries'), 'summary', '/my/teams', STAFF, 140,
         PLUS_ONLY, subtitle=_lt('History per team, from the team page')),
    # Internal users (e.g. an internal lead therapist on the sideline) keep a
    # way back to the backend — the shell has no website/portal header.
    _nav('backend', _lt('Back-end'), 'backend', '/odoo', {'internal'}, 150,
         PLUS_ONLY, subtitle=_lt('The full Odoo application')),
    # Task 1542: per-device install steps (no banner anywhere — owner).
    _nav('install', _lt('Install the app'), 'install', '/my/app/install', EVERYONE, 160,
         PLUS_ONLY, subtitle=_lt('Add Le Fit Crew to your home screen')),
)

# ---------------------------------------------------------------------------
# Fields and sections
# ---------------------------------------------------------------------------
VISIBILITY_REGISTRY = {
    # Field keys (model + field): hidden => server-side unreadable (tested).
    'patient.dob': {'include': TP, 'model': 'sports.patient', 'field': 'date_of_birth'},
    'patient.age': {'include': TP, 'model': 'sports.patient', 'field': 'age'},
    'patient.allergies': {'include': TP, 'model': 'sports.patient', 'field': 'allergies'},
    'patient.internal_notes': {'include': TP, 'model': 'sports.patient',
                               'field': 'team_info_notes'},
    'patient.contacts': {'include': TP, 'model': 'sports.patient', 'field': 'contact_ids'},
    # Home sections.
    'home.team_status': {'include': STAFF},
    'home.upcoming': {'include': STAFF},
    # Therapist working surface: /my/clinics denies everyone else server-side.
    'home.clinic_teaser': {'include': TP},
    # Task 1542 — team page sections / actions. Each one is ALSO gated in the
    # template by the controller's existing server-side value (the model or
    # route check that refuses the action), so the registry can only HIDE:
    #   team.announcement.edit  + team._user_can_edit_announcement()
    #   team.add_player         + the add_link route's own predicate
    #   team.request_add        + NOT that predicate (the request route
    #                             refuses users who may add directly)
    #   team.activities         + can_view_activities (mail.activity ACLs)
    #   team.pending_removals   + can_remove_on_team (_may_remove_from_team)
    'team.announcement.edit': {'include': TP},
    'team.add_player': {'include': TP},
    'team.request_add': {'include': STAFF},
    'team.activities': {'include': STAFF},
    'team.pending_removals': {'include': TP},
}


def is_visible(spec, roles):
    """include any-of, exclude none-of; exclude wins."""
    roles = frozenset(roles or ())
    if roles & frozenset(spec.get('exclude') or ()):
        return False
    return bool(roles & frozenset(spec.get('include') or ()))


def visible_nav(roles, placement, ctx=None):
    """Registry entries visible to ``roles`` at ``placement``, in order."""
    ctx = ctx or {}
    entries = [
        entry for entry in NAV_REGISTRY
        if placement in entry['placement']
        and is_visible(entry, roles)
        and (entry.get('requires') is None or entry['requires'](ctx))
    ]
    return sorted(entries, key=lambda entry: entry['sequence'])


def can(key, roles):
    """``sc_can`` — may this role set SEE ``key``? Unknown keys raise (typos
    must fail loudly, not silently hide a section)."""
    return is_visible(VISIBILITY_REGISTRY[key], roles)
