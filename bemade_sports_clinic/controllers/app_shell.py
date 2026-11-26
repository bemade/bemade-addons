"""Portal app shell (task 1538, epic #1535) — P1a.

Task 1541 (P4): the clinic portal is the app only. Every clinic ``/my``
page renders the app shell for a user who holds a clinic app role (coach,
head coach, therapist, head therapist, doctor, clinic admin: ``STAFF`` in
``models/sc_app_roles.py``) — whatever the kit's ``bemade_portal_kit.enabled``
switch says (the switch stays the kit's: its own pages and the other apps
keep their off mode). A logged-in user without a clinic role gets « Pas
d'accès » (``sc_no_access``, 403): ``sc_app_page`` gates the GET pages,
``AppShellMixin._sc_render(app_template, values)`` renders them.

P1b (task 1542) adds:

* the server autosave pattern — ``POST /my/app/save/<model>/<id>`` driven by
  declarative save specs (task 5199: the route and the spec format moved to
  bemade_portal_kit; the clinic's specs are ``sc_save_specs()``, registered
  through ``portal.kit._pk_save_specs()``);
* the installable app (manifest, service worker, offline and install
  pages; tasks 1542 / 1543). Task 5201 (kit P6): it is the kit addon
  ``bemade_portal_kit_pwa``'s now, same URLs; the clinic brings its
  branding (company fields filled by ``models/sc_app_pwa.py``) and its
  hooks (start URL, shortcuts, offline style).
"""
import functools
import json
import logging
import re
from datetime import timedelta
from urllib.parse import urlencode

from dateutil.relativedelta import relativedelta
import werkzeug.exceptions

from odoo import Command, _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.tools import format_date, format_datetime, html2plaintext, plaintext2html

from odoo.addons.bemade_portal_kit.controllers.pk_app import PortalKitApp
from odoo.addons.bemade_portal_kit.controllers.pk_shell import PortalKitShell
from odoo.addons.bemade_portal_kit.tools import (
    pk_contact_href, pk_display, pk_display_key, pk_draft_props, pk_field_props, pk_form_props, pk_fragment_key,
    pk_now_ms,
)

from ..models import sc_app_nav, sc_app_roles
from ..models.patient import IDENTITY_CONFIRM_KEY, IDENTITY_FIELDS
from ..models.patient_injury import STAGE_ORDER
from .access_control_mixin import (
    AccessControlMixin, parse_portal_date,
)

_logger = logging.getLogger(__name__)

# Task 5200 (kit P5): the switch, the theme choice, /my/app/pref and its
# preferences are the kit's (controllers/pk_shell.py, portal.kit hooks).
_TRUTHY = ('1', 'true', 'yes', 'on')
# ---------------------------------------------------------------------------
# Server autosave (task 1542, filled by task 1539) — WHAT may be saved field
# by field, and BY WHOM. Task 5199 (P4a): the route (``POST
# /my/app/save/<model>/<id>``) and the spec format moved to the kit
# (bemade_portal_kit/tools/save.py documents every key). The clinic's specs
# are built by ``sc_save_specs()`` below and registered per database through
# ``portal.kit._pk_save_specs()`` (models/sc_app_roles.py); ``mail.activity``
# is the kit's spec, with the clinic's rules in its two hooks.
# ---------------------------------------------------------------------------
_TP_ROLES = sc_app_roles.TP
# Task 1603: what an applied follow-up proposal may write (on top of the
# save spec's role allowlist and check), and how many changes at once.
PROPOSAL_FIELDS = {
    # Task 1670: the last active injury resolved also proposes the statuses
    # (applied together as one « sc_status » save — the pair rule).
    'sports.patient': ('predicted_return_date', 'return_date', 'match_status', 'practice_status'),
    # Task 1631: a backward move proposes clearing the resolution date.
    'sports.patient.injury': ('predicted_resolution_date', 'resolution_date'),
}
PROPOSAL_MAX_CHANGES = 50
SC_PROPOSAL_SESSION_KEY = 'sc_pending_proposal'
_STAFF_ROLES = sc_app_roles.STAFF
_TEXT_TYPES = ('char', 'text', 'html')
_VALID_STATUS_PAIRS = {('yes', 'yes'), ('no', 'yes'), ('no', 'no_contact'), ('no', 'no')}
_STATUS_FIELDS = ('match_status', 'practice_status')


def sc_state_options(env, country):
    """Task 1594: the province choices of ``country`` — Canada's while the
    player has no country (the clinic's players) — as [('', ''), (id, name)…].
    A country without provinces offers the blank choice only."""
    if not country:
        country = env['res.country'].search([('code', '=', 'CA')], limit=1)
    states = env['res.country.state'].search(
        [('country_id', '=', country.id)], order='name') if country else env['res.country.state']
    return [('', '')] + [(state.id, state.name) for state in states]


def sc_country_options(env):
    """Task 1594: the country choices — blank, Canada, then every other
    country by name."""
    countries = env['res.country'].search([], order='name')
    canada = countries.filtered(lambda country: country.code == 'CA')
    return [('', '')] + [(country.id, country.name) for country in canada + (countries - canada)]


def sc_file_size(size, env=None):
    """Task 1586: a file size for an attachment row — « 512 B », « 2.1 KB »,
    « 3.0 MB » (« 2,1 Ko » in fr_CA). ``env`` gives the decimal separator;
    the unit follows the request's language."""
    size = int(size or 0)
    if size < 1024:
        return _("%s B", size)
    if size < 1024 * 1024:
        value, unit = size / 1024, 'kb'
    else:
        value, unit = size / (1024 * 1024), 'mb'
    text = '%.1f' % value
    if env is not None and env.lang:
        point = env['res.lang']._get_data(code=env.lang).decimal_point or '.'
        text = text.replace('.', point)
    return _("%s KB", text) if unit == 'kb' else _("%s MB", text)


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


def _record_value(model, value):
    """The record of ``model`` a select posted (empty = an empty recordset);
    an unknown or malformed id is refused as an invalid value."""
    if value in ('', None, False):
        return model
    try:
        record = model.browse(int(value)).exists()
    except (TypeError, ValueError):
        record = None
    if not record:
        raise ValidationError(_("Invalid value."))
    return record


def _date_value(value):
    """Task 1640: a malformed date or a year outside 1900..9999 is refused
    with « Please enter a valid date. » (shared with the legacy routes)."""
    return parse_portal_date(value)


# -- mail.activity (owner review 2026-10-11: the activity page's pencil card) --
# Task 5199 (P4a): the kit's spec (bemade_portal_kit/tools/activity.py); the
# clinic's act / assign rules are its hooks (models/sc_app_roles.py).


# -- sports.quick.note (owner review 2026-10-11: notepad pencil cards) -------
_QUICK_NOTE_LINKS = ('team_id', 'patient_id', 'injury_id', 'event_id')


def _quick_note_portal():
    from .quick_note_portal import QuickNotePortal
    return QuickNotePortal()


def _quick_note_check(ctrl, note):
    portal = _quick_note_portal()
    portal._check_quick_note_access()
    portal._get_own_note(note.id)


def _quick_note_permission(ctrl, note):
    return note.sudo().user_id == request.env.user


def _quick_note_write(ctrl, note, field, value):
    """/my/notepad/<id>/update's rules, one field at a time: a non-empty
    text; a link id outside the therapist's pickers is dropped."""
    portal = _quick_note_portal()
    record = portal._get_own_note(note.id)
    if field == 'note':
        if not (value or '').strip():
            raise ValidationError(_("Please enter a note."))
        record.write({'note': value})
    else:
        vals = portal._clean_link_vals({field: str(value or '')}, portal._quick_note_pickers())
        record.write({field: vals[field]})
    return {}


def _quick_note_display(note, field):
    note = note.sudo()
    if field == 'patient_id':
        return note.patient_id._portal_list_name() if note.patient_id else ''
    if field == 'injury_id':
        return note.injury_id.display_name or ''
    return None


# -- sports.event.timesheet (owner review 2026-10-11: timesheet pencil cards) -
_TIMESHEET_TIMES = ('travel_start', 'coverage_start', 'coverage_end', 'travel_end')


def _timesheet_check(ctrl, timesheet):
    """/my/sc/timesheet/<id>/edit's rules: a therapist, their OWN timesheet,
    never once invoiced."""
    if not ctrl._is_tp_or_system():
        raise AccessError(_("You don't have permission to edit timesheets."))
    if timesheet.sudo().user_id != request.env.user:
        raise AccessError(_("You can only edit your own timesheets."))
    if timesheet.sudo().state == 'invoiced':
        raise UserError(_('This timesheet is invoiced and cannot be edited.'))


def _timesheet_write(ctrl, timesheet, field, value):
    timesheet.write({field: ctrl._parse_portal_datetime(value) if value else False})
    return {}


def _timesheet_read(timesheet, field):
    return AppShellPortal._sc_local_input(timesheet[field])


def _timesheet_display(timesheet, field):
    value = timesheet[field]
    return format_datetime(timesheet.env, value, tz=request.env.user.tz or None,
                           dt_format='EEE d MMM · HH:mm') if value else ''


# -- sports.event (owner review 2026-10-11: the event page's pencil card) -----
_EVENT_TIMES = ('date_start', 'date_end', 'therapist_start', 'therapist_end')
# Task 1608: a new event start sets the end this long after it (legacy portal).
_EVENT_DEFAULT_HOURS = 2


def _csv_ids(value):
    try:
        return [int(part) for part in str(value or '').split(',') if part.strip()]
    except ValueError:
        raise ValidationError(_("Invalid value.")) from None


def sc_event_team_choices(event_sudo=None):
    """Review fixes 2026-10-18 b (#1608, owner decision): the teams an event
    form offers to a user who may create / edit events — EVERY team (an
    archived one would drop out of the search if ``sports.team`` ever gets
    an ``active`` flag), plus the event's current ones. sudo: listing only —
    the user's READ access to teams (record rules) is unchanged."""
    teams = request.env['sports.team'].sudo().search([], order='name')
    if event_sudo:
        teams |= event_sudo.sudo().team_ids
    return teams


def sc_event_team_ids_check(ids, current_ids=()):
    """The posted team ids of an event form, checked: each one is a team the
    form offers (``sc_event_team_choices``) or already on the event. The
    one-organization rule stays the model's (``_check_team_ids``)."""
    ids = list(dict.fromkeys(ids or ()))
    known = set(request.env['sports.team'].sudo().search([('id', 'in', ids)]).ids) | set(current_ids or ())
    if any(team_id not in known for team_id in ids):
        raise ValidationError(_("One of the selected teams does not exist any more."))
    return ids


def _event_check(ctrl, event):
    """/my/event/<id>/save's rule: therapists (portal or internal) and
    system admins only; record rules still apply to the write."""
    user = request.env.user
    if not (user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
            or user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
            or user.has_group('base.group_system')):
        raise AccessError(_("You don't have permission to edit events."))


def _event_write(ctrl, event, field, value):
    if field == 'name':
        value = (value or '').strip()
        if not value:
            raise ValidationError(_("Please fill in all required fields."))
        event.write({'name': value})
    elif field == 'event_type':
        event.write({'event_type': value})
    elif field in _EVENT_TIMES:
        if not value:
            raise ValidationError(_("Please fill in all required fields."))
        moment = fields.Datetime.to_datetime(ctrl._parse_portal_datetime(value))
        vals = {field: moment}
        # Task 1608: the coverage times follow the event times as in the
        # legacy portal — a new start moves the coverage start to it, the end
        # to start + 2 h and the coverage end to that end; a new end moves
        # the coverage end to it when it was empty or earlier. Saved together
        # and answered under « also » so the card's fields follow.
        if field == 'date_start' and moment:
            end = moment + timedelta(hours=_EVENT_DEFAULT_HOURS)
            vals.update({'therapist_start': moment, 'date_end': end, 'therapist_end': end})
        elif field == 'date_end' and moment:
            coverage_end = event.sudo().therapist_end
            if not coverage_end or coverage_end < moment:
                vals['therapist_end'] = moment
        event.write(vals)
        also = [name for name in vals if name != field]
        if also:
            return {'also_fields': also}
    elif field == 'venue_id':
        event.write({'venue_id': int(value) if value else False})
    elif field == 'description':
        text = (value or '').strip()
        event.write({'description': plaintext2html(text) if text else False})
    elif field == 'team_ids':
        current = event.sudo().team_ids.ids
        ids = sc_event_team_ids_check(_csv_ids(value), current)
        # Only when it changed (the save route's rule: an unchanged m2m still
        # runs the team record rules).
        if set(ids) != set(current):
            # Review fixes 2026-10-24: new teams on an event with assignees
            # assign them there — the assignment rule applies.
            staff = event.sudo().assigned_staff_ids.ids
            event.sudo()._sc_check_assignment(request.env.user, staff, staff, current, ids)
            # Review fixes 2026-10-18 b (#1608): any team (checked above), so
            # sudo — the team's partner / organization are read by the
            # event's computes; the one-organization constraint still runs.
            event.sudo().write({'team_ids': [Command.set(ids)]})
    elif field == 'assigned_staff_ids':
        # Review fixes 2026-10-24: checked BEFORE the sudo write (treatment
        # professionals only; another team's event: clinic admin only).
        ids = _csv_ids(value)
        event_sudo = event.sudo()
        event_sudo._sc_check_assignment(
            request.env.user, event_sudo.assigned_staff_ids.ids, ids,
            event_sudo.team_ids.ids, event_sudo.team_ids.ids)
        # sudo: portal users cannot read other users (the save route's rule;
        # access enforced by the check).
        event_sudo.write({'assigned_staff_ids': [Command.set(ids)]})
    return {}


def _event_read(event, field):
    event = event.sudo()
    if field in _EVENT_TIMES:
        return AppShellPortal._sc_local_input(event[field])
    if field in ('team_ids', 'assigned_staff_ids'):
        return ','.join(str(i) for i in event[field].ids)
    if field == 'venue_id':
        return event.venue_id.id or ''
    if field == 'description':
        return html2plaintext(event.description or '').strip()
    return event[field] or ''


def _event_display(event, field):
    event = event.sudo()
    if field in _EVENT_TIMES:
        return format_datetime(event.env, event[field], tz=request.env.user.tz or None,
                               dt_format='EEE d MMM · HH:mm') if event[field] else ''
    if field in ('team_ids', 'assigned_staff_ids'):
        return ', '.join(event[field].mapped('name'))
    if field == 'description':
        return html2plaintext(event.description or '').strip()
    return None


# -- sports.patient ----------------------------------------------------------
def _patient_check(ctrl, patient):
    ctrl._check_access_to_patient(patient.id)


def _assignable_teams():
    """The teams the CURRENT user may assign a player to (the player form's
    rule: staffed teams; every team for a clinic administrator)."""
    return AppShellPortal()._team_targets()


def _patient_read(patient, field):
    if field == 'sc_status':
        return '%s:%s' % (patient.match_status or '', patient.practice_status or '')
    if field == 'sc_team_ids':
        # Only the teams this user may assign: the checklist shows (and
        # posts back) those; the player's other teams are not theirs to touch.
        mine = patient.sudo().team_ids & _assignable_teams()
        return ','.join(str(team_id) for team_id in sorted(mine.ids))
    return AppShellPortal._pk_save_value(patient, field, raw=True)


def _patient_display(patient, field):
    if field == 'sc_team_ids':
        return ', '.join(patient.sudo().team_ids.mapped('name'))
    return None


def _patient_write(ctrl, patient, field, value):
    """/my/player/save's rules, one field at a time (task 1539). Task 1611:
    the heading (app bar, hero) and the status chips refresh as read
    fragments (``refresh``) — no ad-hoc ``heading`` / ``stage`` payload."""
    extra = {}
    if field == 'sc_team_ids':
        # Owner review 2026-10-10 (inline Teams card): add / remove ONLY the
        # teams this user may assign; the player's other teams are kept.
        try:
            selected = {int(part) for part in (value or '').split(',') if part.strip()}
        except ValueError:
            raise ValidationError(_("Invalid value.")) from None
        allowed = _assignable_teams()
        current = patient.sudo().team_ids
        patient.write({'team_ids': [Command.set(
            ((current - allowed) | allowed.filtered(lambda t: t.id in selected)).ids)]})
        return extra
    if field == 'sc_status':
        # Match / practice are ONE save (the pair constraint): « no:no ».
        match, _sep, practice = (value or '').partition(':')
        if (match, practice) not in _VALID_STATUS_PAIRS:
            raise ValidationError(_("Invalid combination of match and practice status."))
        patient.write({'match_status': match, 'practice_status': practice})
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
    if field in ('last_consultation_date', 'return_date', 'predicted_return_date'):
        # Task 1603: « Retour prévu » too (empty = cleared).
        patient.write({field: _date_value(value)})
        return extra
    if field == 'country_id':
        # Task 1594: a province of another country goes with the change; the
        # open card gets the new country's province choices in place.
        country = _record_value(patient.env['res.country'], value)
        vals = {'country_id': country.id or False}
        if patient.state_id and patient.state_id.country_id != country:
            vals['state_id'] = False
        patient.write(vals)
        extra['also_fields'] = ['state_id']
        extra['also_options'] = {'state_id': sc_state_options(patient.env, country)}
        return extra
    if field == 'state_id':
        # Task 1594: the province must belong to the player's country; picked
        # while no country is set, it sets its country too.
        state = _record_value(patient.env['res.country.state'], value)
        vals = {'state_id': state.id or False}
        if state and patient.country_id and state.country_id != patient.country_id:
            raise ValidationError(_("This province does not belong to the player's country."))
        if state and not patient.country_id:
            vals['country_id'] = state.country_id.id
            extra['also_fields'] = ['country_id']
        patient.write(vals)
        return extra
    patient.write({field: _clean_text(value)})
    return extra


def _patient_context(ctrl, patient, field, kw):
    """Task 1639: the identity guard applies to everyone working through the
    app (internal users included). Task 1600: a confirmed identity
    correction (``confirm=1``) is recorded on the file by the model."""
    context = {'sc_identity_guard': True}
    if field in IDENTITY_FIELDS and kw.get('confirm') == '1':
        context[IDENTITY_CONFIRM_KEY] = True
    return context


def _patient_confirm(ctrl, patient, field, value, kw):
    """Task 1600: changing an existing name / date of birth is an explicit,
    confirmed step — the 428 payload (``confirm``, message, old, new,
    detail; the kit's autosave field shows it) until the field's confirm
    banner re-posts with ``confirm=1``."""
    if field not in IDENTITY_FIELDS:
        return None
    return ctrl._sc_identity_confirm_needed(patient, field, value)


def _patient_before_write(ctrl, patient, field):
    """Task 1656: the teams before a player's teams save (a removal may end
    the viewer's own access)."""
    return patient.sudo().team_ids if field == 'sc_team_ids' else None


def _patient_after_write(ctrl, patient, field, teams_before):
    """Task 1656: the viewer removed the team that gave them access — the
    answer is ``{ok, lost_access, message}`` only (``replace``)."""
    if teams_before is None:
        return None
    lost = ctrl._sc_lost_access_payload(patient, teams_before)
    return dict(lost, replace=True) if lost else None


def _patient_propose(patient, field):
    """Task 1603: Retour prévu changed by hand -> align the active injuries'
    predicted resolution dates (a follow-up proposal)."""
    if field == 'predicted_return_date':
        return patient._injuries_alignment_for(patient.predicted_return_date)
    return None


def _patient_hint(patient, field):
    """Task 1601: the training recommendation's « Updated on … by … » stamp."""
    if field == 'training_recommendation':
        return patient.last_training_recommendation_info or ''
    return None


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
    return AppShellPortal._pk_save_value(injury, field, raw=True)


def _injury_display(injury, field):
    """The read view of an inline injury card (owner decision 2026-10-11):
    the virtual date reads « N/A » or the date; visibility reads in words."""
    env = injury.env
    if field == 'sc_injury_date':
        if injury.injury_date_na:
            return env._("N/A")
        return format_date(env, injury.injury_date) if injury.injury_date else ''
    if field == 'hidden_from_coaches':
        return env._("Hidden from coaches") if injury.hidden_from_coaches else env._("Visible to coaches")
    return None


def _injury_hint(injury, field):
    """Task 1601: the injury notes' « Last note on … by … » stamps refresh in
    place after an autosave too (same mechanism as the training
    recommendation's)."""
    if field == 'external_notes':
        return injury.last_external_note_info or ''
    if field == 'internal_notes':
        return injury.last_internal_note_info or ''
    return None


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
        previous = injury.stage
        # Task 1631: a move to an earlier stage (the card's status pill) is a
        # correction — no date is touched here; the save answers ONE
        # proposal to undo the dates that followed (_injury_propose).
        if STAGE_ORDER.get(stage, 0) < STAGE_ORDER.get(previous, 0):
            injury.write(vals)
            injury._sc_log_moved_back()
            return {'propose_context': {'sc_previous_stage': previous}}
        # « Résoudre »: the stage and the resolution date travel together.
        if stage == 'resolved' and not injury.resolution_date:
            vals['resolution_date'] = fields.Date.context_today(injury)
        verifying = previous == 'unverified' and stage == 'active'
        injury.write(vals)
        if verifying:
            # Task 1612: verifying from the app does what the « Verify »
            # button does — log it and close the « Verify injury » To-Do.
            injury._after_verify()
        # Owner review 2026-10-11: the page shows the date at once.
        # Review fixes 2026-10-18: resolving also clears the predicted date
        # (model write) — the card's field follows.
        also = []
        if 'resolution_date' in vals:
            also.append('resolution_date')
        if stage == 'resolved':
            also.append('predicted_resolution_date')
        return {'also_fields': also} if also else {}
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
    # (the note-history hook logs it as an empty « Cleared » row, owner
    # review 2026-10-14).
    injury.write({field: value if (value or '').strip() else False})
    return {}


def _injury_propose(injury, field):
    """Task 1603: an injury's predicted resolution date or stage changed ->
    keep the player's Retour prévu coherent (follow-up proposals): the last
    active injury resolved proposes the actual return; an active injury's
    date (or a verification) proposes the new latest predicted date."""
    patient = injury.patient_id
    if not patient or field not in ('predicted_resolution_date', 'stage'):
        return None
    patient = patient.with_env(injury.env)
    # Task 1631: a backward move (the write hook passed the previous stage)
    # answers its own proposal, and only it.
    previous = injury.env.context.get('sc_previous_stage')
    if field == 'stage' and previous and STAGE_ORDER.get(injury.stage, 0) < STAGE_ORDER.get(previous, 0):
        return patient._after_injury_moved_back(injury, previous)
    if field == 'stage' and injury.stage == 'resolved':
        return patient._after_last_active_resolved(injury)
    return patient._retour_prevu_after_injury_change(injury)


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
    elif field == 'injury_id':
        # Task 1587: empty = a general note; otherwise one of the note's
        # OWN player's injuries (never trust the posted id).
        injury = False
        if str(value or '').strip():
            try:
                injury_id = int(value)
            except (TypeError, ValueError):
                injury_id = 0
            injuries = note.sudo().patient_id.injury_ids
            if injury_id not in injuries.ids:
                raise ValidationError(_("The selected injury does not belong to this player."))
            injury = injury_id
        note.sudo().write({'injury_id': injury})
    return {}


def _note_display(note, field):
    """Task 1587: the linked injury reads as its diagnosis, « General note »
    when the note is linked to none."""
    if field == 'injury_id':
        injury = note.sudo().injury_id
        return (injury.diagnosis or injury.display_name) if injury else _("General note")
    return None


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


# -- sports.injury.document (task 1616: a document of an injury card) ---------
# The legacy categories « xray » / « mri » read (and are re-saved) as
# « Medical Imaging ».
_DOCUMENT_LEGACY_CATEGORIES = {'xray': 'medical_imaging', 'mri': 'medical_imaging'}


def _document_check(ctrl, document):
    """The injury's (or, unlinked, the player's) access — as the download.
    Task 1432: an archived (portal-deleted) document is gone."""
    doc = document.sudo()
    if not doc.active:
        raise MissingError(_("Record not found."))
    if doc.injury_id:
        ctrl._check_access_to_injury(doc.injury_id.id)
    else:
        ctrl._check_access_to_patient(doc.patient_id.id)


def _document_permission(ctrl, document):
    """Portal therapists hold a READ-ONLY ACL on documents (the upload is
    sudo too): whoever may upload may rename / re-file them. Task 1432
    (owner decision 2026-10-31): only the document's uploader or a clinic
    administrator (``_sc_can_manage``)."""
    user = request.env.user
    if not document.sudo()._sc_can_manage(user):
        return False
    if ctrl._is_clinic_admin():
        return True
    return bool(ctrl._is_treatment_professional() and request.env['portal.kit'].pk_can(
        'documents.upload', user._sc_app_roles(), is_system=user.has_group('base.group_system')))


def _document_read(document, field):
    if field == 'category':
        return _DOCUMENT_LEGACY_CATEGORIES.get(document.category, document.category)
    return AppShellPortal._pk_save_value(document, field, raw=True)


def _document_write(ctrl, document, field, value):
    if field == 'name':
        value = (value or '').strip()
        if not value:
            raise ValidationError(_("Please enter a name."))
        document.sudo().write({'name': value})
    elif field == 'category':
        category = _selection_value(document, field, value)
        if not category:
            raise ValidationError(_("Invalid value."))
        document.sudo().write({'category': category})
    elif field == 'injury_id':
        # Task 1432: re-link to one of the player's own injuries, or none
        # (a player document).
        injury = False
        if value not in (None, False, ''):
            try:
                injury = int(value)
            except (TypeError, ValueError):
                injury = 0
            if injury not in document.sudo().patient_id.injury_ids.ids:
                raise ValidationError(_("The selected injury does not belong to this player."))
        document.sudo().write({'injury_id': injury})
    else:
        document.sudo().write({'description': (value or '').strip() or False})
    return {}


# Task 1611: cross-record read fragments.
def _injury_patient_fragments(injury):
    """An injury's player page / dossier: its card list, the hero, the
    « link to an injury » choices, the play status."""
    return ['sports.patient:%s:*' % injury.patient_id.id] if injury.patient_id else []


def _timesheet_event_fragments(timesheet):
    """A timesheet's event page: the « missing timesheets » banner, the
    timesheet list."""
    return ['sports.event:%s:*' % timesheet.event_id.id] if timesheet.event_id else []


def sc_save_specs():
    """The clinic's save specs ``{model: spec}`` (a fresh dict on each call:
    ``portal.kit._pk_save_specs()`` caches the merged result per database)."""
    return {
    'sports.patient': {
        'fields': {
            # Every staff role, as on today's player form.
            'first_name': _STAFF_ROLES, 'last_name': _STAFF_ROLES,
            'jersey_number': _STAFF_ROLES, 'position': _STAFF_ROLES,
            'email': _STAFF_ROLES, 'phone': _STAFF_ROLES,
            'street': _STAFF_ROLES, 'street2': _STAFF_ROLES,
            'city': _STAFF_ROLES, 'zip': _STAFF_ROLES, 'state_id': _STAFF_ROLES,
            # Task 1594: the legacy form took the country from any staff.
            'country_id': _STAFF_ROLES,
            # Therapists only (a coach posting them gets 403).
            # Task 1633: coaches set it too (a change of an existing one is
            # the confirmed identity correction, task 1600).
            'date_of_birth': _STAFF_ROLES,
            # Task 1630: « Other medical history » (therapists only). Task
            # 1677: the allergies / conditions are lists, saved by the
            # popups' own routes (controllers/app_critical_items.py); the
            # levels are computed, the old details read-only.
            'medical_history_other': _TP_ROLES,
            'team_info_notes': _TP_ROLES, 'training_recommendation': _TP_ROLES,
            'last_consultation_date': _TP_ROLES,
            # Task 1594: the actual return date — never a coach's (the legacy
            # portal had no coach path to it; the backend form is clinic staff).
            'return_date': _TP_ROLES,
            # Task 1603: « Retour prévu », in the header (therapists only).
            'predicted_return_date': _TP_ROLES,
            # Virtual: « match:practice », saved as a pair.
            'sc_status': _TP_ROLES,
            # Virtual: CSV of the assignable teams ticked (owner review
            # 2026-10-10, the player page's Teams card).
            'sc_team_ids': _TP_ROLES,
        },
        'check': _patient_check,
        'write': _patient_write,
        'read': _patient_read,
        'display': _patient_display,
        'hint': _patient_hint,
        'propose': _patient_propose,
        # Tasks 1600 / 1639 / 1656: the identity guard and its confirmation,
        # the lost-access answer of a teams save.
        'context': _patient_context,
        'confirm': _patient_confirm,
        'before_write': _patient_before_write,
        'after_write': _patient_after_write,
        # The player page / dossier: title, hero (initials, teams, the
        # allergy / medical-alert pills and their popups), identity read view
        # (age), memberships, removal actions.
        'refresh': {'*': ['*']},
    },
    'sports.patient.injury': {
        'fields': {
            'sc_injury_date': _STAFF_ROLES,       # virtual: date or 'na'
            'diagnosis': _STAFF_ROLES,            # coach: unverified only
            'external_notes': _TP_ROLES,          # owner 2026-10-25: coaches read only
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
        'display': _injury_display,
        'hint': _injury_hint,
        'propose': _injury_propose,
        # The card (summary, read view), the injury page's title / details,
        # the player's fragments (card order, active list, choices) and the
        # linked-injury name in the treatment notes' meta lines.
        # Task 1740: the dashboard's « À faire » counts and its injury lines
        # (a verified injury leaves « Injuries to verify » at once).
        'refresh': {'*': ['*', _injury_patient_fragments, 'sports.treatment.note:*:meta',
                          'pk.dashboard:todo:*', 'pk.dashboard:todo:*:list']},
    },
    'sports.treatment.note': {
        'fields': {'note': _TP_ROLES, 'date': _TP_ROLES, 'injury_id': _TP_ROLES},
        'check': _note_check,
        'write': _note_write,
        'display': _note_display,
        'sudo_write': True,
        'permission': _note_permission,
        # The note's meta line (date, linked injury) and « modified » stamp.
        'refresh': {'*': ['*']},
    },
    'sports.quick.note': {
        'fields': {name: _TP_ROLES for name in ('note',) + _QUICK_NOTE_LINKS},
        'check': _quick_note_check,
        'write': _quick_note_write,
        'display': _quick_note_display,
        'sudo_write': True,
        'permission': _quick_note_permission,
        # The card's text + link chips.
        'refresh': {'*': ['*']},
    },
    'sports.event.timesheet': {
        'fields': {name: _TP_ROLES for name in _TIMESHEET_TIMES},
        'check': _timesheet_check,
        'write': _timesheet_write,
        'read': _timesheet_read,
        'display': _timesheet_display,
        # The card (when, read lines with the totals), the event page's
        # timesheet section and /my/sc/timesheets' list (date groups).
        'refresh': {'*': ['*', _timesheet_event_fragments, 'page:timesheets:*']},
    },
    'sports.event': {
        'fields': {name: _TP_ROLES for name in (
            'name', 'event_type', 'venue_id', 'team_ids', 'assigned_staff_ids', 'description') + _EVENT_TIMES},
        'check': _event_check,
        'write': _event_write,
        'read': _event_read,
        'display': _event_display,
        # Title, kind chip, read view (when, therapist, staff, teams, venue),
        # « Add My Timesheet », the missing-timesheets banner, the cards.
        'refresh': {'*': ['*', 'sports.event.timesheet:*:*']},
    },
    'sports.patient.contact': {
        'fields': {
            'name': _STAFF_ROLES, 'contact_type': _STAFF_ROLES,
            'mobile': _STAFF_ROLES, 'email': _STAFF_ROLES,
        },
        'check': _contact_check,
        'write': _contact_write,
        'refresh': {'*': ['*']},
    },
    # Task 1616: a document of an injury card — re-filed after a multi-file
    # upload (one category / description applied to all of them).
    'sports.injury.document': {
        'fields': {'name': _TP_ROLES, 'category': _TP_ROLES, 'description': _TP_ROLES,
                   # Task 1432: the player Documents tab re-links it.
                   'injury_id': _TP_ROLES},
        'check': _document_check,
        'write': _document_write,
        'read': _document_read,
        'sudo_write': True,
        'permission': _document_permission,
        # The document row (name, category · date · author, description).
        'refresh': {'*': ['*']},
    },
    }


# The kit's mail.activity spec, with the clinic's role allowlist (every staff
# role, as on the activity page).
SC_ACTIVITY_FIELD_ROLES = ('summary', 'date_deadline', 'user_id', 'note')


# ---------------------------------------------------------------------------
# Read fragments (task 1611) — what refreshes on screen after a save. Task
# 5199 (P4a): moved to the kit (bemade_portal_kit/tools/fragments.py,
# @bemade_portal_kit/js/pk_fragments): ``data-pk-fragment`` regions keyed
# ``pk_fragment_key(record, part)``, the ``X-Pk-Fragments`` request,
# ``PortalKitApp._pk_fragments_response``. The clinic keeps its filler
# (``sc_fill_moved_row_fragments``, registered in
# ``portal.kit._pk_fragment_fillers()``).
# ---------------------------------------------------------------------------


# Task 1607: the list header's sort menu — each option re-opens the CURRENT
# page with the sort parameter set (the other query parameters kept, the
# pager reset: the order changes what page 1 holds).
_SC_PAGER_SUFFIX_RE = re.compile(r'/page/\d+/?$')
# Never carried by a sort link: the pager and a POST round-trip's flash.
_SC_SORT_DROP_ARGS = ('page', 'success', 'error', 'error_files')


def sc_sort_options(path, args, param, options, current, drop=()):
    """``[{key, label, url, active}]`` for ``options`` ``[(key, label)]``:
    ``path`` (pager suffix dropped) + ``args`` (a werkzeug MultiDict) with
    ``param=key``, minus ``drop`` (and the pager / flash arguments);
    ``active`` marks ``current``."""
    base = _SC_PAGER_SUFFIX_RE.sub('', path or '') or '/'
    skip = {param, *_SC_SORT_DROP_ARGS, *drop}
    keep = [(key, value) for key, value in (args.items(multi=True) if args else ())
            if key not in skip and value not in (None, '')]
    return [{
        'key': key,
        'label': label,
        'url': '%s?%s' % (base, urlencode(keep + [(param, key)])),
        'active': key == current,
    } for key, label in options]


SC_ROW_KEY_RE = re.compile(r'^sports\.patient:(\d+):row-(\w+)$')


def sc_fill_moved_row_fragments(found, keys):
    """Review 2026-10-21 (#1634): a player card the client still shows in a
    section the fresh render no longer lists it in (a status change moves the
    player from « à surveiller » to « Changements récents ») gets the SAME
    player's fresh card from another section, its row scope rewritten (the
    fragment key, the pill menu ids, the details region id) — so the card the
    user just changed updates in place instead of staying stale (it is kept
    where it is until the next visit, data-pk-fragment-keep)."""
    by_player = {}
    for key, html in found.items():
        match = SC_ROW_KEY_RE.match(key)
        if match:
            by_player.setdefault(match.group(1), (match.group(2), html))
    for key in keys:
        match = SC_ROW_KEY_RE.match(key)
        if not match or key in found or match.group(1) not in by_player:
            continue
        pid, scope = match.groups()
        other, html = by_player[pid]
        html = html.replace('sports.patient:%s:row-%s' % (pid, other), key)
        html = re.sub(r'(pk-pill-sports-patient-%s-\w+)-%s\b' % (pid, re.escape(other)),
                      r'\1-%s' % scope, html)
        html = html.replace('sc-row-detail-%s-%s' % (other, pid), 'sc-row-detail-%s-%s' % (scope, pid))
        found[key] = html





def sc_app_page(endpoint):
    """Task 1541: the clinic app's page gate — under ``@http.route`` on every
    clinic GET page (and every old URL that redirects to one): a logged-in
    user without a clinic app role gets « Pas d'accès » (403) before the
    route runs (no redirect, no record lookup).

    Review 2026-11-26: a user WITH a role whom the page refuses (an
    ``AccessError`` / ``Forbidden`` out of the shared access checks — another
    team's player, event or injury, a therapist-only screen) gets the
    refusal inside the app (``_sc_refused``, HTTP 403) instead of the stock
    website error page. Who is refused does not change."""
    @functools.wraps(endpoint)
    def wrapper(self, *args, **kwargs):
        if not AppShellMixin._sc_app_user():
            return AppShellMixin._sc_no_access()
        try:
            return endpoint(self, *args, **kwargs)
        except (AccessError, werkzeug.exceptions.Forbidden) as exc:
            _logger.info("Clinic app page %s refused for user %s: %s",
                         request.httprequest.path, request.env.uid, exc)
            request.env.cr.rollback()
            return self._sc_refused()
    return wrapper


class AppShellMixin:
    """The clinic app's role gate + the shell's render values. Mixed into
    every CustomerPortal controller that serves a clinic page."""

    @staticmethod
    def _sc_app_user(user=None):
        """Task 1541: does ``user`` (default: the current user) hold a clinic
        app role? The clinic has no off mode: the kit's switch is not read."""
        user = user or request.env.user
        if not user or user._is_public():
            return False
        return bool(set(user._sc_app_roles()) & sc_app_roles.STAFF)

    @staticmethod
    def _sc_no_access():
        """Task 1541: « Pas d'accès » (HTTP 403) for a user without a clinic
        app role."""
        response = request.render('bemade_sports_clinic.sc_no_access', {
            'no_access_theme': AppShellMixin._sc_no_access_theme(),
        })
        response.status_code = 403
        return response

    @staticmethod
    def _sc_no_access_theme():
        """Review 2026-11-26: the theme of « Pas d'accès » — the user's
        own ``pk_theme`` when the theme choice is on and they picked the
        non-default theme (the only choice the app can tell from the
        default), else ``'auto'``: the device's light / dark preference
        (``prefers-color-scheme``, applied in the page)."""
        kit = request.env['portal.kit']
        if kit._pk_theme_choice_enabled():
            theme = kit._pk_effective_theme()
            if theme in ('dark', 'light') and theme != kit._pk_default_theme():
                return theme
        return 'auto'

    def _sc_refused(self):
        """Review 2026-11-26: « Vous n'avez pas accès à cette page. » inside
        the app (its shell and navigation, HTTP 403) — no detail of the
        refused record."""
        response = self._sc_render('bemade_sports_clinic.sc_app_refused', {})
        response.status_code = 403
        return response

    def _sc_booking_enabled(self):
        """The bookings addon (appointment_portal_staff) flags its home card
        through ``_prepare_home_portal_values([])``; absent addon = False."""
        try:
            return bool(self._prepare_home_portal_values([]).get('booking_card_enable'))
        except AccessError:
            return False

    def _sc_activity_user_options_for(self, user):
        """Task 1736 r1: ``activity -> [(id, name)]``, the assignee choices of
        an activity card's inline edit — the same list as the detail page's
        (``_activity_assignable_users_for`` + the current assignee; the save
        route re-checks). The assignable users are searched once per page."""
        cache = {}

        def options(activity):
            if 'users' not in cache:
                cache['users'] = self._activity_assignable_users_for(user)
            users = (cache['users'] | activity.sudo().user_id).sorted('name')
            return [(u.id, u.name) for u in users]
        return options

    @staticmethod
    def _sc_stash_proposal(proposal):
        """Task 1603: a follow-up proposal made by a POST round-trip (an
        injury created with a predicted resolution date) — shown by the
        next shell page (``data-sc-proposal`` on the proposal sheet)."""
        if proposal:
            request.session[SC_PROPOSAL_SESSION_KEY] = proposal

    @staticmethod
    def _sc_pop_proposal():
        """Task 1603: the pending proposal as JSON (popped: shown once), or
        False. A fragment request (task 1611) leaves it for the next page."""
        if PortalKitApp._pk_fragment_keys() is not None or PortalKitApp._pk_guard_probe():
            return False
        proposal = request.session.pop(SC_PROPOSAL_SESSION_KEY, None)
        return json.dumps(proposal) if isinstance(proposal, dict) else False

    def _sc_app_values(self, values, page=None):
        """``values`` + everything ``sc_app_layout`` needs. ``page`` is the
        app template (``module.template``): its navigation — back target,
        context line, crumb trail — comes from the parent registry
        (``models/sc_app_nav.py``, task 1579; ``portal.kit.pk_resolve``, task
        5196); without it the page is top level.

        Task 5200 (kit P5): the generic values (theme, preferences,
        languages, user menu, navigation, help, search, toast) and the
        profile language guard are the kit's
        (``PortalKitShell._pk_shell_values``); the clinic's own come as its
        ``extra``. The guard runs first (a redirect pops nothing)."""
        PortalKitShell._pk_profile_lang_guard()
        user = request.env.user
        roles = user._sc_app_roles()
        is_system = user.has_group('base.group_system')
        kit = request.env['portal.kit']
        ctx = {'booking_card_enable': self._sc_booking_enabled()}
        nav_items = PortalKitShell._pk_nav_items
        # Task 5391: a clinic page is the clinic app's (nav, crumbs, help).
        app = sc_app_nav.SC_APP
        tabs = nav_items(kit.pk_visible_nav(roles, 'tab', ctx, app=app))
        rail = nav_items(kit.pk_visible_nav(roles, 'rail', ctx, app=app))
        plus = nav_items(kit.pk_visible_nav(roles, 'plus', ctx, app=app))
        labels = kit.pk_nav_labels(app=app)
        path = request.httprequest.path
        extra = {
            'pk_app_key': app,
            'sc_app_shell': True,
            'sc_roles': roles,
            # Task 1598: a system admin also sees the TP actions legacy
            # granted them (registry keys flagged ``system``).
            'sc_can': lambda key: kit.pk_can(key, roles, is_system=is_system),
            # Task 1652: the players whose red card pills this page shows
            # (filled while the rows are built) and the viewer's role there.
            'sc_card_med_patients': lambda: request.env['sports.patient'].browse(
                getattr(request, '_sc_card_med_ids', None) or []).exists(),
            'sc_card_med_tp': lambda: bool(self._is_treatment_professional()),
            # Task 1604: today in the user's timezone (the resolve sheet's
            # default and latest resolution date).
            'sc_today_iso': fields.Date.to_string(fields.Date.context_today(user)),
            'pk_tabs': tabs,
            'pk_rail': rail,
            'pk_plus': plus,
            'sc_nav_labels': labels,
            # Task 1592: the app bar's activity clock (its overdue badge is
            # fetched by sc_live_count.js, not computed here).
            'sc_activity_clock': kit.pk_can('app.activity_clock', roles, is_system=is_system),
            # Task 1622: the clock's href carries the page it is tapped on.
            'sc_clock_url': sc_app_nav.clock_url(path, request.httprequest.args),
            # Task 1606: the role line of the user menu.
            'pk_user_role': sc_app_roles.role_label(roles),
            # Task 1660: the help follows the player page's active tab.
            'pk_help_tab': values.get('sc_player_active_tab'),
            # Row builder for list templates (computed in the shell only, so
            # the legacy pages pay nothing for it).
            'sc_team_row': self._sc_team_row,
            # Task 1539: props builders of the autosave field (task 5382: the
            # kit's component and builders, tools/field_props.py).
            'pk_field_props': pk_field_props,
            'pk_draft_props': pk_draft_props,
            'pk_form_props': pk_form_props,
            # Task 1727: today in the user's timezone (a date input's
            # « not in the past » min, e.g. « Retour prévu »).
            'sc_today': fields.Date.to_string(fields.Date.context_today(user)),
            # Owner review 2026-10-10: a card's read view (same strings the
            # save route answers, so an in-place update matches a reload).
            # Task 5381 (P4c2): the kit's helpers (bemade_portal_kit.pk_display_row).
            'pk_display': pk_display,
            'pk_display_key': pk_display_key,
            # Task 1611: read fragments (keys of the regions a save refreshes)
            # and the render stamp the « back » check compares against (task
            # 5199: the kit's names).
            'pk_fragment_key': pk_fragment_key,
            # Task 1607: the sort menu of a list header (sc_list_header).
            'sc_sort_options': lambda param, options, current, drop=(): sc_sort_options(
                path, request.httprequest.args, param, options, current, drop),
            # Task 1585: tap-to-call / tap-to-email hrefs (pk_display_row
            # with ``href_kind``, the event page's staff / organization).
            'pk_contact_href': pk_contact_href,
            # Task 1586: an attachment row's file size.
            'sc_file_size': lambda size: sc_file_size(size, request.env),
            # Task 1589: an activity row's Done / Reschedule / Reassign /
            # Cancel buttons follow the one act rule (the routes re-check).
            'sc_activity_can_act': self._activity_act_access,
            # Task 1736 r1 (owner 2026-11-01): an activity card edited in
            # place — its assignee choices (the per-actor rule of
            # /my/activity/reassign, task 1500, plus the current assignee).
            'sc_activity_assignee_options': self._sc_activity_user_options_for(user),
            # Task 1595: an activity row's related-record links (player /
            # team / event, the injury it is about), access-gated.
            'sc_activity_related': self._sc_activity_related,
            # Owner review 2026-10-14: the related record's name in an
            # activity title is a link too.
            'sc_activity_title_parts': self._sc_activity_title_parts,
            # Task 1603: a follow-up proposal left by a POST round-trip.
            'sc_proposal_json': self._sc_pop_proposal(),
        }
        return self._pk_shell_values(values, page, extra)

    @staticmethod
    def _sc_history_entry(when, author, body, action=None, tone=None, state=None, **extra):
        """Task 1581: ONE history entry (``sc_history_entry``) — the date-time
        in the treatment notes' format (« d MMM y HH:mm », viewer's tz), the
        author's full name, an optional action chip (label + tone), the body
        (empty = « Cleared ») and an optional state (``archived``)."""
        body = (body or '').strip()
        when_label = (request.env['sports.treatment.note']._portal_datetime(when)
                      if when else '')
        entry = {
            'when': when_label,
            'author': author or '',
            'action': str(action) if action else '',
            'tone': tone or 'ghost',
            'body': body,
            'state': state or ('' if body else 'cleared'),
        }
        entry.update(extra)
        return entry

    def _sc_player_tab_url(self, patient_id, tab, team_id=None, clinic=None):
        """The player page on ``tab``, with the team / clinic context."""
        url = '/my/player?player_id=%s' % patient_id
        if team_id:
            url += '&team_id=%s' % team_id
        url = self._with_clinic(url, clinic) if clinic else url
        return url + '&tab=%s' % tab


    @staticmethod
    def _sc_note_injury_options(patient, active_only=False, keep=None):
        """Task 1665: the ONE injury list of the treatment-note forms (add
        AND edit, player page and clinic dossier): every injury of the player,
        the unresolved ones first (newest first), then the resolved ones
        suffixed « (résolue) ». ``[(id, label)]``; sudo: labels only, of the
        player's own injuries (the forms are gated by their routes).

        Task 1721 (review round 1, owner 2026-10-27): ``active_only`` — the
        clinic pane, whose list shows only the active / unverified injuries
        (the resolved ones folded): the same injuries, plus ``keep`` (a
        note's linked injury when editing it, still « (résolue) » if it is)."""
        env = request.env
        injuries = patient.sudo().injury_ids.sorted(
            lambda i: (i.stage == 'resolved', -(i.id or 0)))
        if active_only:
            keep_id = keep.id if keep else 0
            injuries = injuries.filtered(lambda i: i.stage != 'resolved' or i.id == keep_id)
        options = []
        for injury in injuries:
            label = injury.diagnosis or injury.display_name
            if injury.stage == 'resolved':
                label = env._("%s (resolved)", label)
            options.append((injury.id, label))
        return options

    def _sc_note_edit_props(self, note, active_only=False):
        """Task 1587: the pencil edit fields of a treatment-note card — the
        text, the date and the linked injury. Task 1665: the same injury list
        as the add form (all the player's injuries, resolved ones last);
        task 1721: ``active_only`` in the clinic pane (its add form's list,
        plus the note's own injury)."""
        env = request.env
        note_sudo = note.sudo()
        options = [('', env._("General note"))] + self._sc_note_injury_options(
            note_sudo.patient_id, active_only=active_only, keep=note_sudo.injury_id)
        return [
            pk_field_props(note, 'note', env._("Note"), 'textarea'),
            pk_field_props(note, 'date', env._("Date"), 'date'),
            pk_field_props(note, 'injury_id', env._("Injury"), 'select', options=options),
        ]

    # ------------------------------------------------------------------
    # Task 1590 — the inline injury cards, shared by the player page's
    # Injuries tab and the clinic dossier (template sc_injury_card).
    # ------------------------------------------------------------------
    SC_INJURY_TONES = {'unverified': 'yellow', 'active': 'red', 'resolved': 'green'}

    @staticmethod
    def _sc_injury_tp_view(is_tp):
        """A therapist who holds a therapist app role sees the TP fields."""
        return bool(is_tp and request.env.user._sc_app_roles() & sc_app_roles.TP)

    @staticmethod
    def _sc_injury_card_options():
        """The option lists an injury card's autosave fields need."""
        env = request.env
        Injury = env['sports.patient.injury']
        # Task 1631: status, consent and visibility are pill dropdowns now
        # (sports.patient.injury._sc_stage_pill / _sc_flag_pills).
        return {
            'sc_consent_options': [('', '')] + list(
                Injury._fields['parental_consent']._description_selection(env)),
            # Task 1616: the card's Documents (upload sheet, per-document
            # edit) — the deprecated « xray » / « mri » keys left out.
            'sc_document_category_options': [
                (key, label) for key, label
                in env['sports.injury.document']._fields['category']._description_selection(env)
                if key not in _DOCUMENT_LEGACY_CATEGORIES],
        }

    def _sc_injury_card_url(self, injury, team_id=None, clinic=None):
        """Task 1616: where an injury lives in the app — its OPEN card: the
        clinic dossier's when ``clinic`` (a validated clinic) lists it there
        (a current injury of a patient on that clinic's worklist), else the
        player page's Injuries tab (team / clinic context kept)."""
        patient = injury.sudo().patient_id
        if clinic and injury.stage in ('active', 'unverified') and request.env[
                'sports.clinic.attendance'].sudo().search_count([
                    ('event_id', '=', clinic.id), ('patient_id', '=', patient.id)], limit=1):
            return '/my/clinic/%s?patient=%s&tab=dossier&injury=%s#clinic-injury-%s' % (
                clinic.id, patient.id, injury.id, injury.id)
        url = '/my/player?player_id=%s' % patient.id
        try:
            team_id = int(team_id or 0)
        except (TypeError, ValueError):
            team_id = 0
        if team_id:
            url += '&team_id=%s' % team_id
        if clinic:
            url += '&clinic_id=%s' % clinic.id
        return '%s&tab=injuries&injury=%s#injury-%s' % (url, injury.id, injury.id)

    @staticmethod
    def _sc_injury_card_flash(kw):
        """Task 1616: the round-trip messages of an injury card (its
        documents' upload / delete, its deletion, an old injury-page save)
        — on every page listing cards (player page, clinic dossier)."""
        env = request.env
        try:
            count = int(kw.get('count') or 0)
        except (TypeError, ValueError):
            count = 0
        success = {
            'document_uploaded': env._("Document uploaded."),
            'documents_uploaded': env._("%(count)s documents uploaded.", count=count),
            'document_deleted': env._("Document deleted."),
            'injury_deleted': env._("Injury deleted."),
            'injury_updated': env._("Injury updated."),
        }.get(kw.get('success'))
        files = (kw.get('error_files') or '')[:300]
        error = {
            'no_file': env._("Please choose a file."),
            'file_too_large': (
                env._("Nothing was uploaded: these files are over 10 MB: %(files)s", files=files)
                if files else env._("The file is too large (10 MB maximum).")),
            'upload_failed': env._("The upload failed."),
            'invalid_injury': env._("The selected injury does not belong to this patient."),
            'invalid_category': env._("Please choose a valid category."),
            'permission_denied': env._("You do not have permission to do this."),
        }.get(kw.get('error'))
        return {'success': success, 'error': error}

    def _sc_injury_card_documents(self, injuries):
        """Task 1616: the Documents of a whole card list in ONE query —
        ``{injury_id: [{'doc', 'meta'}]}`` (newest first). sudo(): the
        injuries were access-checked by the page (as the former documents
        page did)."""
        env = request.env
        if not injuries:
            return {}
        labels = dict(env['sports.injury.document']._fields['category']._description_selection(env))
        out = {}
        user = env.user
        for doc in env['sports.injury.document'].sudo().search(
                [('injury_id', 'in', injuries.ids)], order='create_date desc, id desc'):
            out.setdefault(doc.injury_id.id, []).append({
                'doc': doc,
                # Task 1432: edit / delete for its uploader or an admin only.
                'can_manage': doc._sc_can_manage(user),
                'meta': ' · '.join(part for part in (
                    labels.get(doc.category, ''), format_date(env, doc.create_date),
                    doc.created_by_id.display_name or '') if part),
            })
        return out

    def _sc_injury_card_row(self, injury, ctx_qs, is_tp, tp_view, opened_id=0, created_id=0,
                            clocks=None, list_url=None, anchor_prefix='injury-', documents=None):
        """One row of an injury card list: ?injury=<id> opens it read-only,
        ?created=<id> (its creator only) opens it in edit mode with the
        « Undo ». Task 1592: ``clocks`` (``_sc_activity_clocks`` of the
        whole card list, ONE query) gives the card its activity clock.
        Task 1616: ``list_url`` (the page listing the card) makes the card's
        own address (``card_url``: where an upload / delete comes back to,
        the card open); ``documents`` (``_sc_injury_card_documents`` of the
        whole list) its Documents."""
        env = request.env
        stages = dict(injury._fields['stage']._description_selection(env))
        when = (format_date(env, injury.injury_date) if injury.injury_date
                else env._("Date unknown"))
        card_url = ('%s&injury=%s#%s%s' % (list_url, injury.id, anchor_prefix, injury.id)
                    if list_url else self._sc_injury_card_url(injury))
        if not list_url:
            list_url = '/my/player?player_id=%s&tab=injuries' % injury.sudo().patient_id.id
        return {
            'id': injury.id,
            # Task 1616: the injury page is retired — the card is the page.
            'url': card_url,
            'title': injury.diagnosis or env._("Injury"),
            'subtitle': ' · '.join(part for part in (when, stages.get(injury.stage, '')) if part),
            'dot': self.SC_INJURY_TONES.get(injury.stage, 'green'),
            'chip': stages.get(injury.stage, ''),
            'hidden': bool(injury.hidden_from_coaches),
            'card_url': card_url,
            'list_url': list_url,
            'documents': (documents or {}).get(injury.id, []),
            'injury': injury,
            'open': injury.id in (opened_id, created_id),
            'created': injury.id == created_id and injury.create_uid == env.user,
            'consent_todo': tp_view and not injury.parental_consent,
            'diagnosis_editable': bool(is_tp or injury.stage == 'unverified'),
            'clock': (clocks or {}).get(injury.id),
        }

    def _sc_render(self, app_template, values):
        """A clinic app page (task 1541: the app only) — « Pas d'accès » for
        a user without a clinic app role."""
        if not self._sc_app_user():
            return self._sc_no_access()
        return self._sc_shell_response(app_template, self._sc_app_values(values, app_template))

    # ------------------------------------------------------------------
    # Task 1611: read fragments (see « Read fragments » above)
    # ------------------------------------------------------------------
    def _sc_shell_response(self, template, values):
        """A shell page: the page itself, or — asked with ``X-Pk-Fragments``
        — the requested read fragments of the SAME render, as JSON (never
        cached; task 5199: the kit's fragment answer)."""
        response = request.render(template, values)
        keys = PortalKitApp._pk_fragment_keys()
        if keys is None:
            return response
        return PortalKitApp._pk_fragments_response(response, keys, values.get('pk_rendered_at'))

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
        # Task 1731: the card's chip says the timesheet is SENT — there is no
        # separate send step (created = submitted), the chip is the proof.
        states = {
            'submitted': env._("Submitted ✓"),
            'invoiced': env._("Billed"),
        }

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
            'state_label': states.get(ts.state) or dict(
                ts._fields['state']._description_selection(env)).get(ts.state, ts.state or ''),
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
            # Task 1584: whose timesheet — the card names the therapist on
            # rows that aren't the viewer's (admins' full event view).
            'own': own,
            'employee': ts.user_id.sudo().name or '',
            'record': ts,
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
    def _sc_team_row(team, with_org=False, clocks=None):
        """Task 1592: ``clocks`` (``_sc_activity_clocks`` of the whole
        list, ONE query) gives the row its activity clock chip."""
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
            'clock': (clocks or {}).get(team.id),
        }

    def _sc_team_clocks(self, teams):
        """Task 1592: the activity clocks of a team list (one query), each
        opening the team page's Activities tab."""
        return self._sc_activity_clocks(
            teams, lambda t: '/my/team?team_id=%s&tab=activities' % t.id)


class AppShellPortal(PortalKitShell, AccessControlMixin, AppShellMixin):

    # ------------------------------------------------------------------
    # /my/home — the app home (« Tableau de bord ») when the shell is
    # active: task 5202 (kit P7), bemade_portal_kit_dashboard's route
    # (PortalKitDashboard.home) draws the clinic's sc_app_home with the
    # clinic's widgets (controllers/app_dashboard.py).
    # ------------------------------------------------------------------

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
        if not (env['portal.kit'].pk_can('home.clinic_teaser', roles)
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

    # ------------------------------------------------------------------
    # Task 5200 (kit P5): /my/app/more, /my/app/settings, /my/app/pref,
    # /my/app/search, /my/account and /my/security are the kit's
    # (PortalKitShell). Its pages are drawn on sc_app_layout
    # (portal.kit._pk_layout) with the clinic's values:
    # ------------------------------------------------------------------
    def _pk_app_values(self, values, page=None):
        # Task 5391: the kit's pages are drawn with the clinic's values in the
        # clinic's app only.
        if request.env['portal.kit']._pk_current_app() != sc_app_nav.SC_APP:
            return super()._pk_app_values(values, page)
        return self._sc_app_values(values, page)

    # ------------------------------------------------------------------
    # /my/app/save/<model>/<id> — the server autosave pattern (task 1542).
    # Task 5199 (P4a): the route and its helpers (``_pk_save_json``,
    # ``_pk_save_value``, ``_pk_save_display``, …) are the kit's
    # (PortalKitApp); the clinic's specs carry its own rules.
    # ------------------------------------------------------------------
    def _sc_lost_access_payload(self, patient, teams_before):
        """Task 1656: the viewer removed the team that gave them access to
        ``patient`` — ``{ok, lost_access, message}`` (no refresh patterns, no
        re-read as the viewer: the page is left), else None."""
        try:
            self._check_access_to_patient(patient.id)
            return None
        except (AccessError, MissingError, UserError):
            pass
        player = patient.sudo()
        removed = teams_before - player.team_ids
        return {
            'ok': True,
            'lost_access': True,
            'message': _("%(player)s removed from %(team)s",
                         player=player._portal_list_name(with_jersey=False),
                         team=', '.join(removed.mapped('name'))),
        }

    @staticmethod
    def _sc_identity_confirm_needed(patient, field, value):
        """The 428 payload asking the client to confirm an identity
        correction (an existing first / last name or date of birth changed
        by a portal user), or None when no confirmation is needed."""
        new = _date_value(value) if field == 'date_of_birth' else (value or '').strip()
        if field != 'date_of_birth' and not new:
            return None  # refused as « required » by the write hook
        changes = patient._sc_identity_corrections({field: new})
        if not changes:
            return None  # same confirm step for every user (owner, 2026-10-12)
        _name, old, new_text = changes[patient.id][0]
        if field == 'date_of_birth':
            old = format_date(patient.env, old) if old else ''
            new_text = format_date(patient.env, new_text) if new_text else ''
        return {
            'confirm': True,
            'message': _("Correct this player's identity?"),
            'old': old,
            'new': new_text,
            # Task 5382: the clinic's line under old → new (it was in the
            # field's template).
            'detail': _("The change will be noted in the player's file."),
        }

    def _pk_save_proposal(self, spec, record, field):
        """Task 1603: the spec's follow-up proposal for this save — for
        therapists only (the kit's builder call otherwise)."""
        if not (request.env.user._sc_app_roles() & _TP_ROLES):
            return None
        return super()._pk_save_proposal(spec, record, field)

    def _sc_apply_changes(self, patient, changes):
        """Task 1603: write the changes of an applied proposal — each one
        re-validated (the proposal allowlist, the save spec's role
        allowlist and check, the record belongs to ``patient``) and written
        by the spec's write hook (the normal save path: validation,
        tracking, history). Raises AccessError / ValidationError; the
        caller runs it in one savepoint (all or nothing). Returns the
        written (record, field) pairs."""
        done = []
        statuses = {}  # task 1670: {field: value} of the player's status rows
        for change in changes:
            if not isinstance(change, dict):
                raise ValidationError(_("Invalid value."))
            model, field = change.get('model'), change.get('field')
            if field not in PROPOSAL_FIELDS.get(model, ()):
                raise AccessError(_("This change cannot be applied here."))
            spec = self._pk_save_spec(model)
            # Match / practice are saved as the player's one « sc_status ».
            allowed_as = 'sc_status' if field in _STATUS_FIELDS else field
            if not spec or not self._pk_save_allowed(spec, allowed_as):
                raise AccessError(_("This change cannot be applied here."))
            try:
                record = request.env[model].browse(int(change.get('id'))).exists()
            except (TypeError, ValueError):
                record = None
            if not record:
                raise MissingError(_("Record not found."))
            owner = record if model == 'sports.patient' else record.sudo().patient_id
            if owner.id != patient.id:
                raise AccessError(_("This change cannot be applied here."))
            spec['check'](self, record)
            if spec.get('sudo_write') and not spec['permission'](self, record):
                raise AccessError(_("You cannot edit this record."))
            value = change.get('value')
            if field in _STATUS_FIELDS:
                statuses[field] = '' if value in (None, False) else str(value)
                continue
            spec['write'](self, record, field, '' if value in (None, False) else str(value))
            done.append((record, field))
        if statuses:
            done += self._sc_apply_statuses(patient, statuses)
        return done

    @staticmethod
    def _sc_past_return_changes(patient, changes):
        """Task 1727: the keys (``model:id:field``, the sheet's row keys) of
        the posted « Retour prévu » changes dated before today (the user's
        timezone); an unparsable value is left to the normal save path."""
        today = fields.Date.context_today(patient)
        keys = []
        for change in changes:
            if not isinstance(change, dict) or change.get('model') != 'sports.patient' \
                    or change.get('field') != 'predicted_return_date':
                continue
            try:
                value = fields.Date.to_date(change.get('value') or False)
            except (TypeError, ValueError):
                continue
            if value and value < today:
                keys.append('sports.patient:%s:predicted_return_date' % change.get('id'))
        return keys

    def _sc_apply_statuses(self, patient, statuses):
        """Task 1670: the match / practice rows of an applied proposal,
        written together through the « sc_status » save (one write, tracked
        like any status change); an invalid pair is refused with the status
        pills' own reason."""
        current = patient.sudo()
        match = statuses.get('match_status', current.match_status)
        practice = statuses.get('practice_status', current.practice_status)
        for name, value in (('match_status', match), ('practice_status', practice)):
            if value not in dict(patient._fields[name].selection):
                raise ValidationError(_("Invalid value."))
        if (match, practice) not in _VALID_STATUS_PAIRS:
            if 'practice_status' in statuses and practice != 'yes' and match == 'yes':
                raise ValidationError(_("Set Match to No first"))
            raise ValidationError(_("Requires Practice: Yes"))
        self._pk_save_spec('sports.patient')['write'](self, patient, 'sc_status', '%s:%s' % (match, practice))
        return [(patient, name) for name in ('match_status', 'practice_status') if name in statuses]

    @http.route(['/my/app/apply-proposal'], type='http', auth='user',
                methods=['POST'], csrf=True, multilang=False)
    def sc_app_apply_proposal(self, patient_id=None, changes=None, **kw):
        """Task 1603: apply a follow-up proposal (the ticked rows of the
        sheet a save answered with ``propose``).

        Body (form-encoded, CSRF enforced): ``patient_id`` (the proposal's
        player) and ``changes`` — JSON ``[{model, id, field, value}, ...]``.
        Every change is re-validated and written through the normal save
        path, all or nothing. Answers JSON:

        * 200 ``{ok, saved: [{model, id, field, value, display,
          write_date}], refresh, saved_at, message}``;
        * 403 ``{error}`` — not a therapist, no access to the player, a
          change outside the proposal allowlist / the caller's roles, or a
          record of another player;
        * 400 ``{error[, message]}`` — malformed body or an invalid value
          (nothing written).
        """
        if not (request.env.user._sc_app_roles() & _TP_ROLES):
            return self._pk_save_json({'error': 'forbidden'}, 403)
        try:
            parsed = json.loads(changes or '')
            patient_id = int(patient_id)
        except (TypeError, ValueError):
            return self._pk_save_json({'error': 'bad_request'}, 400)
        if not isinstance(parsed, list) or not parsed or len(parsed) > PROPOSAL_MAX_CHANGES:
            return self._pk_save_json({'error': 'bad_request'}, 400)
        try:
            patient = self._check_access_to_patient(patient_id)
            # Task 1727: a « Retour prévu » that has passed since the sheet
            # opened (or was proposed past) — ask for a new date, nothing
            # written.
            stale = self._sc_past_return_changes(patient, parsed)
            if stale:
                return self._pk_save_json({
                    'error': 'invalid',
                    'needs_date': stale,
                    'min': fields.Date.to_string(fields.Date.context_today(patient)),
                    'message': _("This date has passed: pick a new predicted return date, today or later."),
                }, 400)
            with request.env.cr.savepoint():
                done = self._sc_apply_changes(patient, parsed)
                for record, _field in done:
                    record.flush_recordset()
            saved, refresh = [], []
            for record, field in done:
                record.invalidate_recordset()
                saved.append({
                    'model': record._name,
                    'id': record.id,
                    'field': field,
                    'value': self._pk_save_value(record, field),
                    'display': self._pk_save_display(record, field),
                    'write_date': fields.Datetime.to_string(record.write_date),
                })
                for pattern in request.env['portal.kit'].pk_refresh_patterns(record, field):
                    if pattern not in refresh:
                        refresh.append(pattern)
            return self._pk_save_json({
                'ok': True,
                'saved': saved,
                'refresh': refresh,
                'saved_at': pk_now_ms(),
                'message': _("Changes applied."),
            })
        except (AccessError, MissingError):
            return self._pk_save_json({'error': 'forbidden'}, 403)
        except (UserError, ValidationError, ValueError) as exc:
            message = exc.args[0] if getattr(exc, 'args', None) else str(exc)
            return self._pk_save_json({'error': 'invalid', 'message': str(message)}, 400)

    # ------------------------------------------------------------------
    # Task 1604 — quick « Vérifier » / « Résoudre » (the injury card row and
    # the injury page header; therapists only)
    # ------------------------------------------------------------------
    def _sc_injury_quick(self, injury_id, run, message):
        """Run ``run(injury)`` for a therapist with access to the injury and
        answer like a save of its ``stage`` (so the page's islands, read
        views and #1611 fragments follow, and #1603's proposal opens):
        ``{ok, write_date, value, display, also: {stage, resolution_date},
        refresh, saved_at, message[, propose]}``; 403 (not a therapist, no
        access), 400 ``{error, message}`` (wrong stage, invalid date —
        nothing written)."""
        if not (request.env.user._sc_app_roles() & _TP_ROLES):
            return self._pk_save_json({'error': 'forbidden'}, 403)
        try:
            injury = self._check_access_to_injury(injury_id)
        except (AccessError, MissingError, UserError):
            return self._pk_save_json({'error': 'forbidden'}, 403)
        try:
            with request.env.cr.savepoint():
                run(injury)
                injury.flush_recordset()
        except (AccessError, MissingError):
            return self._pk_save_json({'error': 'forbidden'}, 403)
        except (UserError, ValidationError, ValueError) as exc:
            message = exc.args[0] if getattr(exc, 'args', None) else str(exc)
            return self._pk_save_json({'error': 'invalid', 'message': str(message)}, 400)
        injury.invalidate_recordset()
        payload = {
            'ok': True,
            'write_date': fields.Datetime.to_string(injury.write_date),
            'value': self._pk_save_value(injury, 'stage'),
            'display': self._pk_save_display(injury, 'stage'),
            'also': {name: {
                'value': self._pk_save_value(injury, name),
                'display': self._pk_save_display(injury, name),
            } for name in ('stage', 'resolution_date', 'predicted_resolution_date')},
            'refresh': request.env['portal.kit'].pk_refresh_patterns(injury, 'stage'),
            'saved_at': pk_now_ms(),
            'live_counts': True,
            'message': message,
        }
        proposal = self._pk_save_proposal(self._pk_save_spec(injury._name), injury, 'stage')
        if proposal:
            payload['propose'] = proposal
        return self._pk_save_json(payload)

    @http.route(['/my/injury/<int:injury_id>/verify'], type='http', auth='user',
                methods=['POST'], csrf=True, multilang=False)
    def sc_injury_quick_verify(self, injury_id, **kw):
        """One tap « Vérifier »: an unverified injury becomes active (the
        model's « Verify » action — logged, its verification To-Do closed)."""
        return self._sc_injury_quick(
            injury_id, lambda injury: injury.action_verify_injury(), _("Injury verified."))

    @http.route(['/my/injury/<int:injury_id>/resolve'], type='http', auth='user',
                methods=['POST'], csrf=True, multilang=False)
    def sc_injury_quick_resolve(self, injury_id, resolution_date=None, from_unverified=None, **kw):
        """« Résoudre » after the confirm sheet: an ACTIVE injury becomes
        resolved on ``resolution_date`` (default today; a past date is
        allowed, a future one refused). Task 1631: the card's status pill
        may also resolve an UNVERIFIED one (``from_unverified=1``: « Résolu »
        picked from « Non vérifié »; its verification To-Do closes, as with
        the former status selector)."""
        allowed = ('active', 'unverified') if from_unverified == '1' else ('active',)

        def run(injury):
            if injury.stage not in allowed:
                raise UserError(_("Only active injuries can be resolved."))
            day = _date_value(resolution_date) or fields.Date.context_today(injury)
            if day > fields.Date.context_today(injury):
                raise ValidationError(_("The resolution date cannot be in the future."))
            injury.action_resolve_injury(resolution_date=day)
        return self._sc_injury_quick(injury_id, run, _("Injury resolved."))


