"""Portal app shell — the clinic's roles, nav entries and visibility keys
(task 1538, epic #1535; registries moved to ``bemade_portal_kit``, task 5196).

How the new portal decides WHAT TO SHOW. Read this before adding a screen, a
menu entry, a field or a role.

The machinery (role resolution, the visibility rule, ``pk_can``,
``pk_visible_nav``) is the kit's ``portal.kit`` model
(``bemade_portal_kit/models/portal_kit.py``). This file holds the clinic's
CONTENT, registered through ``portal.kit``'s hooks below — per database, so
an addon's entries exist only where it is installed.

Roles
-----
A user holds a SET of roles (``res.users._sc_app_roles()`` =
``_pk_roles()`` -> frozenset). One person may hold several — a coach who is
also a therapist, later a coach who is also a parent. A role is resolved
from:

* ``_pk_roles()``  role -> ``groups`` (group xmlids, any-of), and/or
  ``staff_roles``: the ``sports.team.staff.role`` values (any-of) the
  user's partner holds on any team (``res.users._pk_extra_roles``).

Active today: coach, head_coach, therapist, head_therapist, doctor,
clinic_admin, internal. RESERVED (declared, mapped to nothing yet): teacher,
parent, player, secretary. **Adding a future role = give it a group mapping in
``_pk_roles`` + mention it in the registry entries that concern it. No
template edit.** ``internal`` alone does not put a user in the app shell
(``'app': False``, see ``portal.kit.pk_app_roles()``): an internal user
without any clinic role keeps the stock portal.

Visibility rule (every registry below)
--------------------------------------
``include`` (any-of) and ``exclude`` (none-of). An entry is visible when the
user's roles intersect ``include`` AND do not intersect ``exclude`` — exclude
WINS: an entry excluded for ``coach`` stays hidden for a coach who is also a
therapist.

Registries
----------
* ``_pk_nav()``: app navigation. ``placement`` says where an entry appears
  — ``tab`` (phone bottom bar), ``rail`` (laptop left rail), ``plus`` (the
  « Plus » page). ``requires`` is an optional callable(ctx) -> bool for
  feature gates (e.g. the bookings addon's own entry). Templates render
  ``pk_visible_nav(roles, placement, ctx)`` and never branch on groups.
* ``_pk_visibility()``: fields and page sections, asked from QWeb with
  ``sc_can('patient.medical_alerts')``. A key that names ``model`` + ``field`` is a
  field key: whatever it hides from a role MUST already be unreadable for that
  role server-side (field ``groups=`` / ACL / record rule) — the tests assert
  it. **The registry decides what is SHOWN, never what is ALLOWED**; security
  stays in ACLs and record rules.

System administrators (task 1598)
---------------------------------
``base.group_system`` is not a role (it maps to no shell entry on its own),
but the legacy pages granted a system admin the therapist ACTIONS paired
with an ``_is_tp_or_system()``-style server value (add a player directly,
edit the announcement, remove a player…). A key flagged ``'system': True``
is therefore also visible to a system admin (``pk_can(..., is_system=True)``),
whatever their roles — a coach who is also a system admin gets « Add »,
not nothing. ``exclude`` still wins. Plain coaches are unaffected: the
flag only ever widens for ``is_system``. Only flag ACTION keys whose
template gate is a server value that is already True for a system admin.
"""
from odoo import api, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import pk_nav

from . import sc_app_nav

_lt = LazyTranslate(__name__)

# ---------------------------------------------------------------------------
# Roles (names only: the mapping is ``_pk_roles`` below)
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

# Shorthands for the registries below (every role but ``internal`` is an app
# role: ``EVERYONE`` == ``env['portal.kit'].pk_app_roles()`` on a clinic
# database).
STAFF = frozenset({'coach', 'head_coach', 'therapist', 'head_therapist',
                   'doctor', 'clinic_admin'})
TP = frozenset({'therapist', 'head_therapist', 'doctor', 'clinic_admin'})
EVERYONE = frozenset(role for role in ALL_ROLES if role != 'internal')

# Placements (constants, not inline literals: babel's term extractor picks up
# stray string literals that follow an _lt() call in the same argument list).
TAB_RAIL = ('tab', 'rail')
RAIL_PLUS = ('rail', 'plus')
PLUS_ONLY = ('plus',)


class SportsClinicPortalKit(models.AbstractModel):
    _inherit = 'portal.kit'

    # -----------------------------------------------------------------------
    # Roles
    # -----------------------------------------------------------------------
    @api.model
    def _pk_roles(self):
        roles = dict(super()._pk_roles())
        roles.update({
            'coach': {'groups': ('bemade_sports_clinic.group_portal_team_coach',)},
            'head_coach': {'staff_roles': ('head_coach',)},
            'therapist': {'groups': _TP_GROUPS},
            'head_therapist': {'staff_roles': ('head_therapist',)},
            'doctor': {'staff_roles': ('doctor',)},
            'clinic_admin': {'groups': ('bemade_sports_clinic.group_sports_clinic_admin',)},
            # Any backend user; not an app role on its own.
            'internal': {'groups': ('base.group_user',), 'app': False},
            # Reserved: no group yet. A later task only fills the tuple.
            'teacher': {'groups': ()},
            'parent': {'groups': ()},
            'player': {'groups': ()},
            'secretary': {'groups': ()},
        })
        return roles

    # -----------------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------------
    @api.model
    def _pk_nav(self):
        return list(super()._pk_nav()) + [
            # « Équipes » opens the full teams list; the dashboard (/my/home) is the
            # login landing page, reached from the logo (owner review 2026-10-10).
            # Owner review 2026-10-10: phone tabs = Teams, Players, Notepad,
            # Activities, More; Clinic / Events / Timesheets live in « More » on the
            # phone and stay always visible on the laptop rail, above « More ».
            pk_nav('teams', _lt('Teams'), 'teams', '/my/teams', STAFF, 10, TAB_RAIL),
            pk_nav('players', _lt('Players'), 'players', '/my/players', STAFF, 20, TAB_RAIL),
            pk_nav('notepad', _lt('Notepad'), 'note', '/my/notepad', TP, 30, TAB_RAIL,
                   subtitle=_lt('Your quick notes')),
            pk_nav('activities', _lt('Activities'), 'activities', '/my/activities', STAFF, 40,
                   TAB_RAIL),
            pk_nav('clinic', _lt('Clinic'), 'clinic', '/my/clinics', TP, 50, RAIL_PLUS),
            pk_nav('events', _lt('Events and calendar'), 'calendar', '/my/events', STAFF, 60,
                   RAIL_PLUS, subtitle=_lt('Games, practices, clinics')),
            pk_nav('timesheets', _lt('Timesheets'), 'timesheet', '/my/sc/timesheets', TP, 70,
                   RAIL_PLUS, subtitle=_lt('Event coverage')),
            pk_nav('more', _lt('More'), 'more', '/my/app/more', EVERYONE, 90, TAB_RAIL),
            # « Plus » only.
            pk_nav('digests', _lt('Daily summaries'), 'summary', '/my/teams', STAFF, 140,
                   PLUS_ONLY, subtitle=_lt('History per team, from the team page')),
            # Internal users (e.g. an internal lead therapist on the sideline) keep a
            # way back to the backend — the shell has no website/portal header.
            pk_nav('backend', _lt('Back-end'), 'backend', '/odoo', {'internal'}, 150,
                   PLUS_ONLY, subtitle=_lt('The full Odoo application')),
            # Task 1542: per-device install steps (no banner anywhere — owner).
            pk_nav('install', _lt('Install the app'), 'install', '/my/app/install', EVERYONE, 160,
                   PLUS_ONLY, subtitle=_lt('Add Le Fit Crew to your home screen')),
        ]

    # -----------------------------------------------------------------------
    # Fields and sections
    # -----------------------------------------------------------------------
    @api.model
    def _pk_visibility(self):
        keys = dict(super()._pk_visibility())
        keys.update({
            # Field keys (model + field): hidden => server-side unreadable (tested).
            # Task 1633: coaches too (their teams' players — the coach record rule).
            'patient.dob': {'include': STAFF, 'model': 'sports.patient', 'field': 'date_of_birth'},
            'patient.age': {'include': STAFF, 'model': 'sports.patient', 'field': 'age'},
            # Task 1630: the allergy / medical-alert pills — every staff role reads
            # them (a coach: only the non-urgent / urgent ones, the template's rule;
            # editing is the therapists' pencil, gated by ``is_treatment_prof``).
            'patient.medical_alerts': {'include': STAFF, 'model': 'sports.patient',
                                       'field': 'allergy_level'},
            # « Other medical history » (the Infos tab): therapists only.
            'patient.medical_history': {'include': TP, 'model': 'sports.patient',
                                        'field': 'medical_history_other'},
            'patient.internal_notes': {'include': TP, 'model': 'sports.patient',
                                       'field': 'team_info_notes'},
            'patient.contacts': {'include': TP, 'model': 'sports.patient', 'field': 'contact_ids'},
            # Therapist working surface: /my/clinics denies everyone else server-side.
            # Task 1624: the live « Clinics today » chip of the « Today » widget.
            'home.clinic_teaser': {'include': TP},
            # Task 1624 — the dashboard widgets (models/sc_dashboard.py WIDGETS) and
            # the « To do » lines. Each line is ALSO bound by its data's access
            # (record rules, _may_remove_from_team) — the registry only hides.
            'dashboard.today': {'include': STAFF},
            'dashboard.todo': {'include': STAFF},
            'dashboard.recent_changes': {'include': STAFF},
            'dashboard.watch': {'include': STAFF},
            'dashboard.announcements': {'include': STAFF},
            'dashboard.indicators': {'include': STAFF},
            'dashboard.coverage': {'include': STAFF},
            # Review round 1 (owner 2026-10-29): my followed players (every staff
            # role) and my past events without a timesheet (therapists only).
            'dashboard.followed': {'include': STAFF},
            'dashboard.missing_timesheets': {'include': TP},
            'dashboard.todo.activities': {'include': STAFF},
            'dashboard.todo.verify': {'include': TP},
            'dashboard.todo.removals': {'include': TP, 'system': True},
            # Review round 1 (owner 2026-10-29): therapists update the « Retour
            # prévu » dates — the overdue ones are their to-do, not a coach's.
            'dashboard.todo.returns': {'include': TP},
            # Review round 1: « Suivre / Ne plus suivre » a player (personal).
            'patient.follow': {'include': STAFF},
            # Task 1542 — team page sections / actions. Each one is ALSO gated in the
            # template by the controller's existing server-side value (the model or
            # route check that refuses the action), so the registry can only HIDE:
            #   team.announcement.edit  + team._user_can_edit_announcement()
            #   team.add_player         + the add_link route's own predicate
            #   team.request_add        + NOT that predicate (the request route
            #                             refuses users who may add directly)
            #   team.activities         + can_view_activities (mail.activity ACLs)
            #   team.pending_removals   + can_remove_on_team (_may_remove_from_team)
            'team.announcement.edit': {'include': TP, 'system': True},
            'team.add_player': {'include': TP, 'system': True},
            'team.request_add': {'include': STAFF},
            'team.activities': {'include': STAFF},
            'team.pending_removals': {'include': TP, 'system': True},
            # Task 1539 (P2) — players, injuries, notes, documents, activities. Same
            # rule: each key is ALSO gated in the template by the controller's
            # existing server-side value (the legacy page's ``is_treatment_prof`` /
            # ``can_*`` flags), and the save route refuses the field server-side
            # (SAVE_REGISTRY per-role allowlists, controllers/app_shell.py).
            'injury.internal_notes': {'include': TP, 'model': 'sports.patient.injury',
                                      'field': 'internal_notes'},
            'players.create': {'include': TP},
            'players.add_to_team': {'include': TP},
            'patient.status.edit': {'include': TP},
            'patient.training.edit': {'include': TP},
            # Task 1603: « Retour prévu » in the player header.
            'patient.return.edit': {'include': TP},
            'patient.edit.tp_fields': {'include': TP},
            # Owner decision 2026-10-10: coaches see and edit emergency contacts too
            # (their ACL / record rules already allowed it; deleting stays TP).
            'patient.contacts.tab': {'include': STAFF},
            'patient.notes.tab': {'include': TP},
            'patient.activities.tab': {'include': STAFF},
            'patient.remove': {'include': TP, 'system': True},
            'patient.request_removal': {'include': STAFF},
            'injury.stage.edit': {'include': TP},
            'injury.visibility.edit': {'include': TP},
            'injury.tp_fields': {'include': TP},
            'injury.delete': {'include': TP},
            'injury.all_stages': {'include': TP},
            'documents.upload': {'include': TP},
            'documents.delete': {'include': TP},
            'notes.add': {'include': TP},
            'activities.reassign': {'include': STAFF},
            # Task 1592 — the app bar's activity clock (+ its overdue count route).
            'app.activity_clock': {'include': STAFF},
        })
        return keys

    # -----------------------------------------------------------------------
    # Pages (parent / back / crumbs: models/sc_app_nav.py)
    # -----------------------------------------------------------------------
    @api.model
    def _pk_pages(self):
        return list(super()._pk_pages()) + sc_app_nav.sc_pages(self)


# ---------------------------------------------------------------------------
# Role label (task 1606: the head of the user menu)
# ---------------------------------------------------------------------------
# Most significant first, per family: the menu shows the user's top
# therapist-side role and top coach-side role (« Thérapeute · Entraîneur »
# for a coach who is also a therapist). Reserved roles get a label when they
# get a group.
# Two parallel tuples (no string literal next to an _lt() call: babel's term
# extractor would pick it up, see the placements above).
_ROLE_LABEL_KEYS = ('clinic_admin', 'head_therapist', 'doctor', 'therapist',
                    'head_coach', 'coach')
_ROLE_LABEL_TERMS = (
    _lt('Clinic administrator'), _lt('Head Therapist'), _lt('Doctor'), _lt('Therapist'),
    _lt('Head Coach'), _lt('Coach'),
)
ROLE_LABELS = dict(zip(_ROLE_LABEL_KEYS, _ROLE_LABEL_TERMS))
ROLE_LABEL_FAMILIES = (_ROLE_LABEL_KEYS[:4], _ROLE_LABEL_KEYS[4:])


def role_label(roles):
    """The role line of the user menu (translated), or '' for none."""
    roles = frozenset(roles or ())
    labels = []
    for family in ROLE_LABEL_FAMILIES:
        for role in family:
            if role in roles:
                labels.append(str(ROLE_LABELS[role]))
                break
    return ' · '.join(labels)
