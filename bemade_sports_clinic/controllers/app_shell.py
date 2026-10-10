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
  (``sc_sw_register.js``) then unregisters every registration of the worker
  a device still holds (the kill switch).

Task 1543: the worker and the manifest cover the WHOLE origin (scope ``/``).
A session in a non-default website language is served under ``/<lang>/my/``
(e.g. ``/en/my/team``), which a ``/my/`` scope never saw offline. The PWA
routes themselves stay ``multilang=False`` (stable, unprefixed URLs).
"""
import json
from datetime import timedelta

from dateutil.relativedelta import relativedelta

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
_TRUTHY = ('1', 'true', 'yes', 'on')
# The ONLY fields /my/app/pref may write, with their allowed values.
PREF_FIELDS = {
    'sc_nav_mode': ('back', 'crumbs'),
    'sc_theme': ('dark', 'light'),
}
# ---------------------------------------------------------------------------
# Server autosave (task 1542, filled by task 1539) — WHAT may be saved field
# by field, and BY WHOM.
#
#   SAVE_REGISTRY = {
#       '<model>': {
#           'fields': {'field_a': ROLES, ...},       # per-role allowlist: the
#                                                    # field is refused (403)
#                                                    # unless the caller holds
#                                                    # one of ROLES. A plain
#                                                    # tuple = any app role.
#           'check': callable(controller, record),   # raises AccessError /
#                                                    # MissingError to refuse;
#                                                    # reuse AccessControlMixin
#           'write': callable(controller, record, field, value) -> dict | None
#                                                    # optional write hook (the
#                                                    # controller's existing
#                                                    # rules: validation, pairs,
#                                                    # normalisation). Raises
#                                                    # UserError/ValidationError
#                                                    # -> 400; returns extra
#                                                    # payload keys (``message``).
#           'read': callable(record, field) -> value # optional, for VIRTUAL
#                                                    # fields (not on the model)
#           'sudo_write': True,                      # the hook writes as sudo …
#           'permission': callable(controller, record) -> bool,
#                                                    # … which REQUIRES this
#                                                    # permission callable,
#                                                    # checked before any write
#                                                    # (asserted at import).
#       },
#   }
#
# The write runs AS THE USER unless a spec declares ``sudo_write`` (only where
# the user genuinely lacks the ACL for the write — portal therapists have a
# read-only ACL on treatment notes): ACLs, record rules and the models' own
# write guards still apply on top of ``check``. Role-restricted fields are
# refused server-side even when the ORM would allow them (a coach holds a
# write ACL on injuries, yet may not change their stage).
# ---------------------------------------------------------------------------
_TP_ROLES = sc_app_roles.TP
_STAFF_ROLES = sc_app_roles.STAFF
_TEXT_TYPES = ('char', 'text', 'html')
_VALID_STATUS_PAIRS = {('yes', 'yes'), ('no', 'yes'), ('no', 'no_contact'), ('no', 'no')}
# The status pair's values (virtual field ``sc_status``), in display order.
SC_STATUS_KEYS = ('yes:yes', 'no:yes', 'no:no_contact', 'no:no')
# Dot / chip tone of a player's stage (same tones as the lists' rows).
SC_STAGE_TONES = {'no_play': 'red', 'practice_ok': 'yellow', 'healthy': 'green'}


def _clean_text(value):
    value = (value or '').strip()
    return value or False


def _selection_value(record, field, value):
    keys = [key for key, _label in record._fields[field]._description_selection(record.env)]
    if value in ('', None, False):
        return False
    if value not in keys:
        raise ValidationError(_("Invalid value."))
    return value


def _date_value(value):
    if value in ('', None, False):
        return False
    try:
        return fields.Date.to_date(value)
    except (TypeError, ValueError):
        raise ValidationError(_("Please enter a valid date.")) from None


# -- sports.patient ----------------------------------------------------------
def _patient_check(ctrl, patient):
    ctrl._check_access_to_patient(patient.id)


def _patient_read(patient, field):
    if field == 'sc_status':
        return '%s:%s' % (patient.match_status or '', patient.practice_status or '')
    return AppShellPortal._sc_save_value(patient, field, raw=True)


def _patient_write(ctrl, patient, field, value):
    """/my/player/save's rules, one field at a time (task 1539)."""
    extra = {}
    if field == 'sc_status':
        # Match / practice are ONE save (the pair constraint): « no:no ».
        match, _sep, practice = (value or '').partition(':')
        if (match, practice) not in _VALID_STATUS_PAIRS:
            raise ValidationError(_("Invalid combination of match and practice status."))
        patient.write({'match_status': match, 'practice_status': practice})
        # Owner review 2026-10-10: the page updates the hero's status pill in
        # place from this (sc_app_ui.js, « sc:saved »).
        stage = patient.stage or 'healthy'
        labels = dict(patient._fields['stage']._description_selection(patient.env))
        extra['stage'] = {'tone': SC_STAGE_TONES.get(stage, 'green'),
                          'label': labels.get(stage, '')}
        return extra
    if field in ('first_name', 'last_name'):
        # Task 1537: a rename goes through the ORM as the user (the partner
        # mirror is sudo'd in the model); a name is never blanked.
        value = (value or '').strip()
        if not value:
            raise ValidationError(_("First name and last name are required"))
        patient.write({field: value})
        return extra
    if field == 'jersey_number':
        # Task 1421: the model normalises (« #12 » -> « 12 »); a clash with an
        # active teammate is a SOFT warning, shown inline under the field.
        patient.write({'jersey_number': _clean_text(value)})
        if patient.sudo()._jersey_duplicates():
            extra['message'] = patient._jersey_duplicate_message()
        return extra
    if field == 'date_of_birth':
        dob = _date_value(value)
        if dob:
            today = fields.Date.context_today(patient)
            if dob > today or dob < today - relativedelta(years=120):
                raise ValidationError(_(
                    'Date of Birth must not be in the future and not be more than 120 years ago.'))
        patient.write({field: dob})
        return extra
    if field == 'last_consultation_date':
        patient.write({field: _date_value(value)})
        return extra
    if field == 'state_id':
        try:
            patient.write({field: int(value) if value else False})
        except (TypeError, ValueError):
            raise ValidationError(_("Invalid value.")) from None
        return extra
    patient.write({field: _clean_text(value)})
    return extra


# -- sports.patient.injury ---------------------------------------------------
def _injury_check(ctrl, injury):
    ctrl._check_access_to_injury(injury.id)


def _injury_read(injury, field):
    if field == 'sc_injury_date':
        if injury.injury_date_na:
            return 'na'
        return fields.Date.to_string(injury.injury_date) if injury.injury_date else ''
    if field == 'hidden_from_coaches':
        # The segmented control's values (« Entraîneurs » / « Masquée »).
        return '1' if injury.hidden_from_coaches else '0'
    return AppShellPortal._sc_save_value(injury, field, raw=True)


def _injury_write(ctrl, injury, field, value):
    """/my/injury/save's rules, one field at a time (task 1539)."""
    roles = request.env.user._sc_app_roles()
    if field == 'sc_injury_date':
        # The date and its « N/A » box are one value: 'na' or a date.
        if value == 'na':
            injury.write({'injury_date_na': True, 'injury_date': False})
        else:
            day = _date_value(value)
            if not day:
                raise ValidationError(_("If injury date is not set, the N/A box must be checked."))
            injury.write({'injury_date': day, 'injury_date_na': False})
        return {}
    if field == 'diagnosis':
        # Today's form: a coach may only reword an injury still unverified.
        if not (roles & _TP_ROLES) and injury.stage != 'unverified':
            raise AccessError(_("Only treatment professionals can change a verified diagnosis."))
        injury.write({field: (value or '').strip()})
        return {}
    if field == 'stage':
        stage = _selection_value(injury, field, value)
        if not stage:
            raise ValidationError(_("Invalid value."))
        vals = {'stage': stage}
        # « Résoudre »: the stage and the resolution date travel together.
        if stage == 'resolved' and not injury.resolution_date:
            vals['resolution_date'] = fields.Date.context_today(injury)
        injury.write(vals)
        return {}
    if field == 'hidden_from_coaches':
        injury.write({field: str(value).lower() in _TRUTHY})
        return {}
    if field == 'parental_consent':
        injury.write({field: _selection_value(injury, field, value)})
        return {}
    if field in ('predicted_resolution_date', 'resolution_date'):
        injury.write({field: _date_value(value)})
        return {}
    # Note fields: raw text; an essentially-empty value is a genuine clear
    # (the note-history hook logs nothing for it, task 1404).
    injury.write({field: value if (value or '').strip() else False})
    return {}


# -- sports.treatment.note ---------------------------------------------------
def _note_check(ctrl, note):
    user = request.env.user
    if not (ctrl._is_treatment_professional()
            or user.has_group('bemade_sports_clinic.group_sports_clinic_admin')
            or user.has_group('base.group_system')):
        raise AccessError(_('Only treatment professionals can edit treatment notes.'))
    ctrl._check_access_to_patient(note.sudo().patient_id.id)


def _note_permission(ctrl, note):
    """Task 1413: the author or a clinic admin — nobody else."""
    return note._can_portal_edit(request.env.user)


def _note_write(ctrl, note, field, value):
    """Portal therapists hold a READ-ONLY ACL on treatment notes: every portal
    write goes through sudo AFTER ``_note_permission`` (the route calls it
    first). sudo keeps the uid, so the model's own write() guard still
    refuses a non-author a second time."""
    if field == 'note':
        value = (value or '').strip()
        if not value:
            raise ValidationError(_('Treatment note cannot be empty.'))
        note.sudo().write({'note': value})
    elif field == 'date':
        day = _date_value(value)
        if not day:
            raise ValidationError(_("Please enter a valid date."))
        note.sudo().write({'date': day})
    return {}


# -- sports.patient.contact (the player form's primary emergency contact) ----
def _contact_check(ctrl, contact):
    ctrl._check_access_to_patient(contact.sudo().patient_id.id)
    user = request.env.user
    if not (ctrl._is_treatment_professional()
            or user.has_group('bemade_sports_clinic.group_portal_team_coach')):
        raise AccessError(_("Only treatment professionals and coaches can edit contacts."))


def _contact_write(ctrl, contact, field, value):
    if field == 'name':
        value = (value or '').strip()
        if not value:
            raise ValidationError(_("Name and contact type are required fields"))
        contact.write({'name': value})
    elif field == 'contact_type':
        value = _selection_value(contact, field, value)
        if not value:
            raise ValidationError(_("Name and contact type are required fields"))
        contact.write({'contact_type': value})
    else:
        contact.write({field: _clean_text(value)})
    return {}


SAVE_REGISTRY = {
    'sports.patient': {
        'fields': {
            # Every staff role, as on today's player form.
            'first_name': _STAFF_ROLES, 'last_name': _STAFF_ROLES,
            'jersey_number': _STAFF_ROLES, 'position': _STAFF_ROLES,
            'email': _STAFF_ROLES, 'phone': _STAFF_ROLES,
            'street': _STAFF_ROLES, 'street2': _STAFF_ROLES,
            'city': _STAFF_ROLES, 'zip': _STAFF_ROLES, 'state_id': _STAFF_ROLES,
            # Therapists only (a coach posting them gets 403).
            'date_of_birth': _TP_ROLES, 'allergies': _TP_ROLES,
            'team_info_notes': _TP_ROLES, 'training_recommendation': _TP_ROLES,
            'last_consultation_date': _TP_ROLES,
            # Virtual: « match:practice », saved as a pair.
            'sc_status': _TP_ROLES,
        },
        'check': _patient_check,
        'write': _patient_write,
        'read': _patient_read,
    },
    'sports.patient.injury': {
        'fields': {
            'sc_injury_date': _STAFF_ROLES,       # virtual: date or 'na'
            'diagnosis': _STAFF_ROLES,            # coach: unverified only
            'external_notes': _STAFF_ROLES,
            'stage': _TP_ROLES,
            'internal_notes': _TP_ROLES,
            'predicted_resolution_date': _TP_ROLES,
            'resolution_date': _TP_ROLES,
            'hidden_from_coaches': _TP_ROLES,
            'parental_consent': _TP_ROLES,
        },
        'check': _injury_check,
        'write': _injury_write,
        'read': _injury_read,
    },
    'sports.treatment.note': {
        'fields': {'note': _TP_ROLES, 'date': _TP_ROLES},
        'check': _note_check,
        'write': _note_write,
        'sudo_write': True,
        'permission': _note_permission,
    },
    'sports.patient.contact': {
        'fields': {
            'name': _STAFF_ROLES, 'contact_type': _STAFF_ROLES,
            'mobile': _STAFF_ROLES, 'email': _STAFF_ROLES,
        },
        'check': _contact_check,
        'write': _contact_write,
    },
}


def _validate_save_registry(registry):
    """A spec that writes as sudo MUST carry its permission callable."""
    for model, spec in registry.items():
        assert callable(spec.get('check')), "%s: 'check' is mandatory" % model
        if spec.get('sudo_write'):
            assert callable(spec.get('permission')), (
                "%s: a sudo_write spec requires a 'permission' callable" % model)
            assert callable(spec.get('write')), (
                "%s: a sudo_write spec requires its 'write' hook" % model)

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
            # Task 1539: props builders for the sc_autosave_field component.
            'sc_field_props': self._sc_field_props,
            'sc_draft_props': self._sc_draft_props,
        }
        shell.update(values)
        return shell

    @staticmethod
    def _sc_status_options():
        """Task 1539: the four valid match / practice pairs (patient.py
        constraint) as ONE choice each — the status is always saved as a
        pair (SAVE_REGISTRY virtual field ``sc_status``)."""
        env = request.env
        # Labels first, keys zipped in: babel's extractor would take a
        # literal that follows an _() call in the same list for a term.
        labels = (
            env._("Match + practice"),
            env._("Contact practice"),
            env._("Practice, no contact"),
            env._("No play"),
        )
        return list(zip(SC_STATUS_KEYS, labels))

    @staticmethod
    def _sc_options(pairs):
        """[(key, label)] -> JSON-safe [[str(key), str(label)]]."""
        return [[str(key), str(label)] for key, label in pairs]

    @staticmethod
    def _sc_field_props(record, field, label, input_type='text', **extra):
        """JSON props of a SERVER-mode sc_autosave_field for ``record.field``
        (the value and write_date the save route will compare against)."""
        props = {
            'mode': 'server',
            'model': record._name,
            'recordId': record.id,
            'field': field,
            'writeDate': fields.Datetime.to_string(record.write_date),
            'label': str(label),
            'inputType': input_type,
            'inputId': 'sc_%s_%s_%s' % (record._name.replace('.', '_'), record.id, field),
            'value': AppShellPortal._sc_save_value(record, field),
        }
        if extra.get('options') is not None:
            extra['options'] = AppShellMixin._sc_options(extra['options'])
        for key, value in extra.items():
            if value is not None:
                props[key] = str(value) if key in ('hint', 'placeholder', 'undoMessage') else value
        return json.dumps(props, default=str)

    @staticmethod
    def _sc_draft_props(draft_key, name, label, input_type='text', value='', **extra):
        """JSON props of a DRAFT-mode sc_autosave_field: a real form field
        (``name``) whose typing is kept on the device under ``draft_key``."""
        props = {
            'mode': 'draft',
            'name': name,
            'draftKey': draft_key,
            'label': str(label),
            'inputType': input_type,
            'inputId': 'sc_draft_%s' % name,
            'value': value or '',
        }
        if extra.get('options') is not None:
            extra['options'] = AppShellMixin._sc_options(extra['options'])
        for key, val in extra.items():
            if val is not None:
                props[key] = str(val) if key in ('hint', 'placeholder') else val
        return json.dumps(props, default=str)

    def _sc_render(self, legacy_template, app_template, values):
        """THE per-page switch: the app template in the shell, else today's."""
        if app_template and self._sc_app_shell_active():
            return request.render(app_template, self._sc_app_values(values))
        return request.render(legacy_template, values)

    # ------------------------------------------------------------------
    # Task 1540: timesheet rows (event page + /my/sc/timesheets)
    # ------------------------------------------------------------------
    @staticmethod
    def _sc_local_input(value):
        """A UTC datetime as the user's local ``YYYY-MM-DDTHH:MM`` (the
        value of a datetime-local input)."""
        if not value:
            return ''
        return fields.Datetime.context_timestamp(request.env.user, value).strftime('%Y-%m-%dT%H:%M')

    @staticmethod
    def _sc_hours(value):
        value = value or 0.0
        hours = int(value)
        minutes = int(round((value - hours) * 60))
        if minutes == 60:
            hours, minutes = hours + 1, 0
        return '%d:%02d' % (hours, minutes)

    def _sc_timesheet_row(self, ts):
        """Display + edit values of ONE timesheet (already access-checked by
        the caller's search)."""
        env = request.env
        user = env.user
        tz = user.tz or env.context.get('tz')
        event = ts.event_id.sudo()
        states = dict(ts._fields['state']._description_selection(env))

        def _when(value, fmt='EEE d MMM · HH:mm'):
            return format_datetime(env, value, tz=tz, dt_format=fmt) if value else '—'

        own = ts.user_id.id == user.id
        return {
            'id': ts.id,
            'title': event.name or env._("Event"),
            'when': _when(ts.coverage_start),
            'subtitle': ' · '.join(part for part in (
                ', '.join(event.team_ids.mapped('name')),
                event.partner_id.name or '',
            ) if part),
            'state': ts.state,
            'state_label': states.get(ts.state, ts.state or ''),
            'lines': [
                (env._("Travel Start"), _when(ts.travel_start)),
                (env._("Coverage Start"), _when(ts.coverage_start)),
                (env._("Coverage End"), _when(ts.coverage_end)),
                (env._("Travel End"), _when(ts.travel_end)),
                (env._("Travel Hours"), self._sc_hours(ts.travel_duration)),
                (env._("Coverage Hours"), self._sc_hours(ts.coverage_duration)),
            ],
            'inputs': {
                'travel_start': self._sc_local_input(ts.travel_start),
                'coverage_start': self._sc_local_input(ts.coverage_start),
                'coverage_end': self._sc_local_input(ts.coverage_end),
                'travel_end': self._sc_local_input(ts.travel_end),
            },
            'editable': ts.state != 'invoiced' and own,
            'event_url': '/my/event/%s' % event.id,
        }

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
            order = 'last_player_activity_%s_at desc nulls last, name, id' % role
            if self._is_clinic_admin():
                # Task 1577 (owner decision 2026-09-28): a clinic admin's home
                # lists EVERY team, the ones they staff first; the count and
                # the stat tiles follow the same set.
                teams = self._staffed_first(teams.search([], order=order))
            else:
                teams = teams.search(
                    [('staff_ids.user_ids', '=', user.id)], order=order)
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

    @http.route(['/my/clinics/today/count'], type='http', auth='user', website=True,
                methods=['GET'], multilang=False, sitemap=False)
    def sc_clinics_today_count(self, **kw):
        """The home's « Clinics today » count as JSON, for the teaser chip's
        live poll (review 2026-09-29; same mechanism as the live worklist:
        20 s, visible tab only, backoff on error). Same permission as the
        teaser: the therapist roles (portal, internal, clinic admin) with
        read access to events; never cached."""
        env = request.env
        roles = env.user._sc_app_roles()
        if not (sc_app_roles.can('home.clinic_teaser', roles)
                and env['sports.event'].has_access('read')):
            response = request.make_json_response({'error': 'forbidden'}, status=403)
        else:
            response = request.make_json_response({'count': self._sc_clinics_today_count()})
        response.headers['Cache-Control'] = 'no-store'
        return response

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
                'url': '/my/event/%s?return_url=%%2Fmy%%2Fhome' % event.id,
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
        return request.redirect(self._safe_return_url(redirect, '/my/app/more'))

    # ------------------------------------------------------------------
    # /my/app/save/<model>/<id> — the server autosave pattern (task 1542)
    # ------------------------------------------------------------------
    @staticmethod
    def _sc_save_json(payload, status=200):
        return request.make_json_response(payload, status=status)

    @staticmethod
    def _sc_save_value(record, name, raw=False):
        spec = SAVE_REGISTRY.get(record._name) or {}
        if not raw and spec.get('read'):
            return spec['read'](record, name)
        value = record[name]
        field = record._fields[name]
        if field.type in ('many2one',):
            return value.id or False
        if field.type in ('date', 'datetime'):
            return field.to_string(value) if value else False
        return value

    @classmethod
    def _sc_field_unchanged(cls, record, field, old_value):
        """Does ``record.field`` still hold what the client last saw?"""
        if old_value is None:
            return False
        current = cls._sc_save_value(record, field)
        if current is False or current is None:
            current = ''
        return str(current).strip() == str(old_value).strip()

    @staticmethod
    def _sc_save_allowed(spec, field):
        """Is ``field`` in the spec's allowlist for the CALLER's roles?"""
        allowed = spec.get('fields') or ()
        if field not in allowed:
            return False
        if isinstance(allowed, dict):
            return bool(request.env.user._sc_app_roles() & frozenset(allowed[field]))
        return True

    @http.route(['/my/app/save/<string:model>/<int:record_id>'], type='http', auth='user',
                methods=['POST'], csrf=True, multilang=False)
    def sc_app_save(self, model, record_id, field=None, value=None, write_date=None,
                    old_value=None, **kw):
        """Save ONE field of ONE record, as the user.

        Body (form-encoded, CSRF enforced by the http POST route):
        ``field``, ``value``, ``write_date`` (the value the client last saw),
        optional ``old_value`` (task 1539: the FIELD value the client last
        saw — a record written since, but whose field still holds
        ``old_value``, is not a conflict: e.g. a sibling field of the same
        form was saved a moment ago).
        Answers JSON:

        * 200 ``{ok, write_date, value[, message]}`` — saved (``value`` is the
          stored value, e.g. a normalised jersey number; ``message`` a soft
          warning such as a duplicate jersey number);
        * 409 ``{conflict, current_value, current_write_date, by}`` — the
          record changed since ``write_date`` (nothing written);
        * 403 ``{error}`` — model / field outside ``SAVE_REGISTRY``, a field
          outside the caller's role allowlist, the registry check or
          permission refused, or the ORM refused the write;
        * 400 ``{error}`` — missing parameters or an invalid value.
        """
        spec = SAVE_REGISTRY.get(model)
        if not spec or not field or not self._sc_save_allowed(spec, field):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        if value is None or not write_date:
            return self._sc_save_json({'error': 'bad_request'}, 400)
        record = request.env[model].browse(record_id)
        try:
            if not record.exists():
                raise MissingError(_("Record not found."))
            spec['check'](self, record)
            if spec.get('sudo_write') and not spec['permission'](self, record):
                raise AccessError(_("You cannot edit this record."))
            current = fields.Datetime.to_string(record.write_date)
            if current != write_date and not self._sc_field_unchanged(record, field, old_value):
                return self._sc_save_json({
                    'conflict': True,
                    'current_value': self._sc_save_value(record, field),
                    'current_write_date': current,
                    'by': record.sudo().write_uid.name or '',
                }, 409)
            extra = {}
            # A refused / invalid write leaves nothing behind (a hook may
            # write more than one field).
            with request.env.cr.savepoint():
                if spec.get('write'):
                    extra = spec['write'](self, record, field, value) or {}
                else:
                    if value == '' and record._fields[field].type not in _TEXT_TYPES:
                        value = False
                    record.write({field: value})
                record.flush_recordset()
            record.invalidate_recordset()
            payload = {
                'ok': True,
                'write_date': fields.Datetime.to_string(record.write_date),
                'value': self._sc_save_value(record, field),
            }
            payload.update(extra)
            return self._sc_save_json(payload)
        except (AccessError, MissingError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        except (UserError, ValidationError, ValueError) as exc:
            message = exc.args[0] if getattr(exc, 'args', None) else str(exc)
            return self._sc_save_json({'error': 'invalid', 'message': str(message)}, 400)

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
            # Whole origin (1543): /en/my/... pages belong to the app too.
            'scope': '/',
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
                {'name': labels['teams'], 'url': '/my/teams'},
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
        """The service worker, allowed the whole origin (scope ``/``, task
        1543). ``no-cache`` so a device picks up a new version (or this route's 404, which the page script turns into an
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
            ('Service-Worker-Allowed', '/'),
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


_validate_save_registry(SAVE_REGISTRY)
