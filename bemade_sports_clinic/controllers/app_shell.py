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
import logging
import re
import time
from datetime import timedelta
from urllib.parse import urlencode

from dateutil.relativedelta import relativedelta
import werkzeug.exceptions
from lxml import etree
from lxml import html as lxml_html

from markupsafe import Markup

from odoo import Command, _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.modules.module import get_manifest
from odoo.tools import file_open, format_date, format_datetime, html2plaintext, plaintext2html

from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models import sc_app_nav, sc_app_roles
from ..models.patient import IDENTITY_CONFIRM_KEY, IDENTITY_FIELDS
from ..models.patient_injury import STAGE_ORDER
from .access_control_mixin import AccessControlMixin, parse_portal_date

_logger = logging.getLogger(__name__)

APP_SHELL_PARAM = 'bemade_sports_clinic.app_shell_enabled'
# Task 1602: the dark / light choice. Absent or falsy = forced dark for
# everyone and both theme toggles hidden; the saved ``sc_theme`` is kept and
# applies again once this is on.
THEME_CHOICE_PARAM = 'bemade_sports_clinic.sc_theme_choice_enabled'
_TRUTHY = ('1', 'true', 'yes', 'on')
# The ONLY fields /my/app/pref may write, with their allowed values.
# Task 1579: no navigation setting any more — the screen width decides.
PREF_FIELDS = {
    'sc_theme': ('dark', 'light'),
    # Task 1665: « Recevoir le sommaire quotidien par courriel » (the same
    # per-user preference as the backend « Daily Morning Briefing »).
    'digest_daily_enabled': ('1', '0'),
}
# Task 1665: the boolean preferences, posted as '1' / '0'.
PREF_BOOLEANS = ('digest_daily_enabled',)
# Task 1588: « Plus › Langue » — the user's profile language (``res.users.lang``),
# allowed values = the request's frontend languages (checked at post time).
PREF_LANG = 'lang'
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
#           'hint': callable(record, field) -> str | None
#                                                    # optional (task 1601): the
#                                                    # field's fresh « updated on
#                                                    # … by … » stamp, answered
#                                                    # as ``hint`` so the page
#                                                    # updates it in place; None
#                                                    # = the field has no stamp.
#           'refresh': {field | '*': [entry, ...]}   # task 1611: the READ
#                                                    # FRAGMENTS of the page a
#                                                    # save of ``field`` makes
#                                                    # stale (``'*'`` key: every
#                                                    # field). An entry is a part
#                                                    # of THIS record's keys
#                                                    # (``'hero'`` ->
#                                                    # ``<model>:<id>:hero``,
#                                                    # ``'*'`` = all of them), a
#                                                    # full key pattern
#                                                    # (``'sports.treatment.note:*:meta'``)
#                                                    # or callable(record) -> [patterns]
#                                                    # (another record's keys).
#                                                    # Answered as ``refresh``.
#           'propose': callable(record, field) -> dict | None
#                                                    # task 1603: a FOLLOW-UP
#                                                    # PROPOSAL after the save
#                                                    # (therapists only), answered
#                                                    # as ``propose`` — see
#                                                    # models/patient_return_proposal.py
#                                                    # and /my/app/apply-proposal.
#           'live_counts': True,                     # task 1611: the save also
#                                                    # refreshes the app bar's
#                                                    # live counters (overdue
#                                                    # activities badge).
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
# Task 1603: what an applied follow-up proposal may write (on top of the
# SAVE_REGISTRY role allowlist and check), and how many changes at once.
PROPOSAL_FIELDS = {
    'sports.patient': ('predicted_return_date', 'return_date'),
    # Task 1631: a backward move proposes clearing the resolution date.
    'sports.patient.injury': ('predicted_resolution_date', 'resolution_date'),
}
PROPOSAL_MAX_CHANGES = 50
SC_PROPOSAL_SESSION_KEY = 'sc_pending_proposal'
_STAFF_ROLES = sc_app_roles.STAFF
_TEXT_TYPES = ('char', 'text', 'html')
_VALID_STATUS_PAIRS = {('yes', 'yes'), ('no', 'yes'), ('no', 'no_contact'), ('no', 'no')}


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


def sc_contact_href(kind, value):
    """Task 1585: the tap-to-call / tap-to-email href of a shown phone or
    email (``kind`` = ``'tel'`` / ``'mailto'``), or None when there is
    nothing to dial or write to. A phone keeps only ``+`` and its digits
    (« +1 (555) 010-0123 » -> ``tel:+15550100123``). Same rule in the
    browser: static/src/js/sc_contact_href.js."""
    value = (value or '').strip() if isinstance(value, str) else ''
    if not value:
        return None
    if kind == 'tel':
        digits = re.sub(r'[^0-9+]', '', value)
        return 'tel:%s' % digits if re.search(r'[0-9]', digits) else None
    if kind == 'mailto':
        return 'mailto:%s' % value
    return None


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
def _activity_check(ctrl, activity):
    if not ctrl._activity_act_access(activity):
        raise AccessError(_("You do not have access to this activity."))


def _activity_permission(ctrl, activity):
    return ctrl._activity_act_access(activity)


def _activity_write(ctrl, activity, field, value):
    """/my/activity/update's rules, one field at a time; sudo (coaches hold a
    read-only mail.activity ACL — the access check is the authorization)."""
    record = activity.sudo()
    if field == 'summary':
        value = (value or '').strip()
        if not value:
            raise ValidationError(_("Please fill in all required fields."))
        record.write({'summary': value})
    elif field == 'date_deadline':
        day = _date_value(value)
        if not day:
            raise ValidationError(_("Please fill in all required fields."))
        record.write({'date_deadline': day})
    elif field == 'note':
        record.write({'note': plaintext2html(value) if (value or '').strip() else False})
    elif field == 'user_id':
        try:
            user = request.env['res.users'].browse(int(value))
        except (TypeError, ValueError):
            user = request.env['res.users']
        if user != record.user_id:
            if user not in ctrl._activity_assignable_users_for(request.env.user):
                raise ValidationError(_("You cannot assign this activity to that user."))
            record.write({'user_id': user.id})
    return {}


def _activity_read(activity, field):
    activity = activity.sudo()
    if field == 'note':
        return html2plaintext(activity.note or '').strip()
    if field == 'user_id':
        return activity.user_id.id or False
    if field == 'date_deadline':
        return fields.Date.to_string(activity.date_deadline) if activity.date_deadline else ''
    return activity[field] or ''


def _activity_display(activity, field):
    activity = activity.sudo()
    if field == 'note':
        return html2plaintext(activity.note or '').strip()
    if field == 'user_id':
        return activity.user_id.name or ''
    return None


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
    if field == 'allergy_epipen':
        # Task 1630: the segmented « Yes / No » control's values.
        return '1' if patient.allergy_epipen else '0'
    if field == 'sc_team_ids':
        # Only the teams this user may assign: the checklist shows (and
        # posts back) those; the player's other teams are not theirs to touch.
        mine = patient.sudo().team_ids & _assignable_teams()
        return ','.join(str(team_id) for team_id in sorted(mine.ids))
    return AppShellPortal._sc_save_value(patient, field, raw=True)


def _patient_display(patient, field):
    if field == 'sc_team_ids':
        return ', '.join(patient.sudo().team_ids.mapped('name'))
    if field in ('allergy_level', 'medical_alert_level'):
        # Task 1630: « Not specified » for no level.
        return patient._sc_level_label(patient[field])
    if field == 'allergy_epipen':
        return patient.env._("Yes") if patient.allergy_epipen else patient.env._("No")
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
    if field in ('allergy_level', 'medical_alert_level'):
        # Task 1630: « » = Not specified. Task 1653: refused once set (the
        # model); « None known » empties and locks the details / EpiPen —
        # answered along (also), so the popup's fields follow in place.
        new_level = _selection_value(patient, field, value)
        # Owner review 2026-10-22: « None known » clears — a one-shot
        # snapshot first, so the answer can offer « Undo ».
        family = 'allergy' if field == 'allergy_level' else 'medical_alert'
        snapshot = patient._sc_medical_snapshot(family) if new_level == 'none' else None
        patient.write({field: new_level})
        if snapshot:
            extra['undo'] = patient._sc_medical_undo_offer(family, snapshot)
        others = dict(patient._SC_MEDICAL_PAIRS)[field]
        extra['also_fields'] = list(others)
        extra['also_disabled'] = {name: patient[field] == 'none' for name in others}
        return extra
    if field == 'allergy_epipen':
        patient.write({field: str(value).lower() in _TRUTHY})
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
    return AppShellPortal._sc_save_value(injury, field, raw=True)


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
    """The injury's (or, unlinked, the player's) access — as the download."""
    doc = document.sudo()
    if doc.injury_id:
        ctrl._check_access_to_injury(doc.injury_id.id)
    else:
        ctrl._check_access_to_patient(doc.patient_id.id)


def _document_permission(ctrl, document):
    """Portal therapists hold a READ-ONLY ACL on documents (the upload is
    sudo too): whoever may upload may rename / re-file them."""
    user = request.env.user
    return bool(ctrl._is_treatment_professional() and sc_app_roles.can(
        'documents.upload', user._sc_app_roles(), is_system=user.has_group('base.group_system')))


def _document_read(document, field):
    if field == 'category':
        return _DOCUMENT_LEGACY_CATEGORIES.get(document.category, document.category)
    return AppShellPortal._sc_save_value(document, field, raw=True)


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


SAVE_REGISTRY = {
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
            # Task 1630: the allergy / medical-alert levels, details, EpiPen
            # and « Other medical history » replace the free-text allergies
            # (coaches read some of them, never write: 403).
            'allergy_level': _TP_ROLES, 'allergy_details': _TP_ROLES,
            'allergy_epipen': _TP_ROLES, 'medical_alert_level': _TP_ROLES,
            'medical_alert_details': _TP_ROLES, 'medical_history_other': _TP_ROLES,
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
        # The player page / dossier: title, hero (initials, teams, the
        # allergy / medical-alert pills and their popups), identity read view
        # (age), memberships, removal actions.
        'refresh': {'*': ['*']},
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
        'display': _injury_display,
        'hint': _injury_hint,
        'propose': _injury_propose,
        # The card (summary, read view), the injury page's title / details,
        # the player's fragments (card order, active list, choices) and the
        # linked-injury name in the treatment notes' meta lines.
        'refresh': {'*': ['*', _injury_patient_fragments, 'sports.treatment.note:*:meta']},
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
    'mail.activity': {
        'fields': {
            'summary': _STAFF_ROLES, 'date_deadline': _STAFF_ROLES,
            'user_id': _STAFF_ROLES, 'note': _STAFF_ROLES,
        },
        'check': _activity_check,
        'write': _activity_write,
        'read': _activity_read,
        'display': _activity_display,
        'sudo_write': True,
        'permission': _activity_permission,
        # Title, state chip, note; the app bar's overdue badge.
        'refresh': {'*': ['*']},
        'live_counts': True,
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
        'fields': {'name': _TP_ROLES, 'category': _TP_ROLES, 'description': _TP_ROLES},
        'check': _document_check,
        'write': _document_write,
        'read': _document_read,
        'sudo_write': True,
        'permission': _document_permission,
        # The document row (name, category · date · author, description).
        'refresh': {'*': ['*']},
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
        assert spec.get('propose') is None or callable(spec['propose']), (
            "%s: 'propose' must be callable(record, field)" % model)
        for field, entries in (spec.get('refresh') or {}).items():
            assert field == '*' or field in (spec.get('fields') or ()), (
                "%s: 'refresh' names an unknown field %r" % (model, field))
            assert all(callable(entry) or isinstance(entry, str) for entry in entries), (
                "%s: a 'refresh' entry is a key pattern or a callable" % model)


# ---------------------------------------------------------------------------
# Read fragments (task 1611) — what refreshes on screen after a save.
#
# A server-built, READ-ONLY region of a shell page carries
# ``data-sc-fragment="<model>:<id>:<part>"`` (``sc_fragment_key(record,
# part)`` in the templates; page-level regions use ``page:<name>:<part>``).
# Keys are unique on the page and stable across renders. A region never holds
# an OWL island (``owl-component``) — mark its read-only parts instead.
#
# * A save answers ``refresh`` (the spec's ``refresh`` map, resolved for the
#   record) — key patterns where ``*`` matches one key segment.
# * The page (static/src/js/sc_fragments.js) matches them against the keys it
#   carries and GETs ITS OWN URL with the ``X-Sc-Fragments: k1,k2`` header:
#   the page route renders exactly as for a reload (same values, same access
#   rules, same QWeb) and ``_sc_shell_response`` answers only those nodes as
#   JSON ``{fragments: {key: outer html}, missing: [...], title, rendered_at}``.
# * The client swaps each node in place, never one holding an OWL island or
#   the focused element (retried once that element loses focus).
# * ``data-sc-fragment-mode="list"`` on a container whose children carry
#   ``data-sc-fragment-item="<key>"``: the live items are kept (their islands
#   survive) and only re-ordered / dropped / added as in the fresh render.
# ---------------------------------------------------------------------------
SC_FRAGMENTS_HEADER = 'X-Sc-Fragments'
SC_FRAGMENTS_MAX = 200
_SC_FRAGMENT_KEY_RE = re.compile(r'^[\w.\-]+(?::[\w.\-*]+)*$')


def sc_fragment_key(record, part):
    """The fragment key of ``part`` of ``record`` (``<model>:<id>:<part>``)."""
    return '%s:%s:%s' % (record._name, record.id, part)


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


def sc_now_ms():
    """Server time in ms (the render stamp and the save's ``saved_at``: both
    on the server clock, so the « back » check never compares two clocks)."""
    return int(time.time() * 1000)


def sc_refresh_patterns(model, record, field):
    """The fragment key patterns a save of ``record.field`` makes stale."""
    spec = SAVE_REGISTRY.get(model) or {}
    refresh = spec.get('refresh') or {}
    base = '%s:%s' % (model, record.id)
    patterns = []
    for entry in list(refresh.get('*', ())) + list(refresh.get(field, ())):
        items = entry(record.sudo()) if callable(entry) else [entry]
        for item in items or ():
            if not item:
                continue
            if ':' not in item:
                item = '%s:%s' % (base, item)
            if item not in patterns:
                patterns.append(item)
    return patterns


def sc_extract_fragments(html, keys):
    """``{key: outer html}`` of the nodes of the rendered page ``html`` whose
    ``data-sc-fragment`` is one of ``keys``, and the document title."""
    tree = lxml_html.document_fromstring(html)
    wanted = set(keys)
    found = {}
    for node in tree.iterfind('.//*[@data-sc-fragment]'):
        key = node.get('data-sc-fragment')
        if key in wanted and key not in found:
            found[key] = etree.tostring(node, encoding='unicode', method='html', with_tail=False)
    title = tree.find('.//title')
    return found, (title.text_content().strip() if title is not None else '')

SC_ROW_KEY_RE = re.compile(r'^sports\.patient:(\d+):row-(\w+)$')


def sc_fill_moved_row_fragments(found, keys):
    """Review 2026-10-21 (#1634): a player card the client still shows in a
    section the fresh render no longer lists it in (a status change moves the
    player from « à surveiller » to « Changements récents ») gets the SAME
    player's fresh card from another section, its row scope rewritten (the
    fragment key, the pill menu ids, the details region id) — so the card the
    user just changed updates in place instead of staying stale (it is kept
    where it is until the next visit, data-sc-fragment-keep)."""
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
        html = re.sub(r'(sc-pill-sports-patient-%s-\w+)-%s\b' % (pid, re.escape(other)),
                      r'\1-%s' % scope, html)
        html = html.replace('sc-row-detail-%s-%s' % (other, pid), 'sc-row-detail-%s-%s' % (scope, pid))
        found[key] = html


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

    @staticmethod
    def _sc_theme_choice_enabled():
        raw = request.env['ir.config_parameter'].sudo().get_param(THEME_CHOICE_PARAM)
        return str(raw or '').strip().lower() in _TRUTHY

    @classmethod
    def _sc_effective_theme(cls, user):
        """The theme the app renders for ``user``: forced dark unless the
        theme choice is enabled (task 1602)."""
        if not cls._sc_theme_choice_enabled():
            return 'dark'
        return user.sc_theme or 'dark'

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

    @staticmethod
    def _sc_guard_probe():
        """Task 1658: this request is a guarded form's fetch (sc_form_guard.js
        sends X-Sc-Guard on the POST, kept across its redirect)."""
        try:
            return request.httprequest.headers.get('X-Sc-Guard') == '1'
        except RuntimeError:  # no request
            return False

    @staticmethod
    def _sc_pop_notification():
        """Task 1583: pop ``request.session['notification']`` (the
        ``{type, title, message}`` dict the POST routes store) into the
        toast payload ``{message, title, tone}`` — tone ``error`` for the
        danger / warning types, ``success`` otherwise — or False. A fragment
        request (task 1611) leaves it for the next real page."""
        if AppShellMixin._sc_fragment_keys() is not None:
            return False
        # Task 1658: a guarded form's fetch (X-Sc-Guard) reads the page it
        # landed on to find a refusal — peek, so the real navigation that
        # follows a success still shows the toast.
        if AppShellMixin._sc_guard_probe():
            notif = request.session.get('notification')
        else:
            notif = request.session.pop('notification', None)
        if not isinstance(notif, dict) or not (notif.get('message') or notif.get('title')):
            return False
        return {
            'message': str(notif.get('message') or ''),
            'title': str(notif.get('title') or ''),
            'tone': 'error' if notif.get('type') in ('danger', 'warning', 'error') else 'success',
        }

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
        if AppShellMixin._sc_fragment_keys() is not None or AppShellMixin._sc_guard_probe():
            return False
        proposal = request.session.pop(SC_PROPOSAL_SESSION_KEY, None)
        return json.dumps(proposal) if isinstance(proposal, dict) else False

    def _sc_app_values(self, values, page=None):
        """``values`` + everything ``sc_app_layout`` needs. ``page`` is the
        app template (``module.template``): its navigation — back target,
        context line, crumb trail — comes from the parent registry
        (``models/sc_app_nav.py``, task 1579); without it the page is top
        level."""
        self._sc_profile_lang_guard()
        user = request.env.user
        roles = user._sc_app_roles()
        is_system = user.has_group('base.group_system')
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
            # Task 1598: a system admin also sees the TP actions legacy
            # granted them (registry keys flagged ``system``).
            'sc_can': lambda key: sc_app_roles.can(key, roles, is_system=is_system),
            # Task 1652: the players whose red card pills this page shows
            # (filled while the rows are built) and the viewer's role there.
            'sc_card_med_patients': lambda: request.env['sports.patient'].browse(
                getattr(request, '_sc_card_med_ids', None) or []).exists(),
            'sc_card_med_tp': lambda: bool(self._is_treatment_professional()),
            # Task 1604: today in the user's timezone (the resolve sheet's
            # default and latest resolution date).
            'sc_today_iso': fields.Date.to_string(fields.Date.context_today(user)),
            'sc_tabs': tabs,
            'sc_rail': rail,
            'sc_plus': plus,
            'sc_nav_labels': labels,
            # Task 1602: forced dark (no toggles) unless the choice is on.
            'sc_theme': self._sc_effective_theme(user),
            'sc_theme_choice': self._sc_theme_choice_enabled(),
            'sc_langs': self._sc_lang_options(),
            'sc_current_url': path + ('?' + query if query else ''),
            'sc_search_url': '/my/players' if any(t['key'] == 'players' for t in rail) else False,
            # Task 1592: the app bar's activity clock (its overdue badge is
            # fetched by sc_live_count.js, not computed here).
            'sc_activity_clock': sc_app_roles.can('app.activity_clock', roles, is_system=is_system),
            # Task 1622: the clock's href carries the page it is tapped on.
            'sc_clock_url': sc_app_nav.clock_url(path, request.httprequest.args),
            'sc_user_initials': initials or '?',
            # Task 1606: the head of the user menu (name + role).
            'sc_user_name': user.name or '',
            'sc_user_role': sc_app_roles.role_label(roles),
            # Task 1542: the device draft store is namespaced by db + uid.
            'sc_db': request.db or '',
            'sc_uid': user.id,
            # Row builder for list templates (computed in the shell only, so
            # the legacy pages pay nothing for it).
            'sc_team_row': self._sc_team_row,
            # Task 1539: props builders for the sc_autosave_field component.
            'sc_field_props': self._sc_field_props,
            # Owner review 2026-10-10: a card's read view (same strings the
            # save route answers, so an in-place update matches a reload).
            'sc_display': lambda record, field: AppShellPortal._sc_save_display(record, field),
            'sc_display_key': lambda record, field: '%s:%s:%s' % (record._name, record.id, field),
            # Task 1611: read fragments (keys of the regions a save refreshes)
            # and the render stamp the « back » check compares against.
            'sc_fragment_key': sc_fragment_key,
            # Task 1607: the sort menu of a list header (sc_list_header).
            'sc_sort_options': lambda param, options, current, drop=(): sc_sort_options(
                path, request.httprequest.args, param, options, current, drop),
            'sc_rendered_at': sc_now_ms(),
            # Task 1585: tap-to-call / tap-to-email hrefs (sc_display_row
            # with ``href_kind``, the event page's staff / organization).
            'sc_contact_href': sc_contact_href,
            # Task 1586: an attachment row's file size.
            'sc_file_size': lambda size: sc_file_size(size, request.env),
            # Task 1589: an activity row's Done / Reschedule / Reassign /
            # Cancel buttons follow the one act rule (the routes re-check).
            'sc_activity_can_act': self._activity_act_access,
            # Task 1595: an activity row's related-record links (player /
            # team / event, the injury it is about), access-gated.
            'sc_activity_related': self._sc_activity_related,
            # Owner review 2026-10-14: the related record's name in an
            # activity title is a link too.
            'sc_activity_title_parts': self._sc_activity_title_parts,
            'sc_draft_props': self._sc_draft_props,
            # Task 1583: the pending session notification (set by a POST
            # round-trip, e.g. « Add to Team ») pops on whichever shell page
            # comes next, as the status toast.
            'sc_notification': self._sc_pop_notification(),
            # Task 1603: a follow-up proposal left by a POST round-trip.
            'sc_proposal_json': self._sc_pop_proposal(),
        }
        shell.update(values)
        nav = sc_app_nav.resolve(
            (page or '').rpartition('.')[2], shell, request.env,
            request_url=shell['sc_current_url'],
            request_return_url=request.httprequest.args.get('return_url'))
        shell.update({
            'sc_parent_url': nav['parent_url'],
            'sc_crumbs': nav['crumbs'],
            'sc_context': nav['context'],
            # Task 1660: the page's help (the app bar « ? », « Aide »).
            'sc_help': request.env['sc.help.article']._sc_help_for(
                (page or '').rpartition('.')[2],
                tab=request.params.get('tab') or shell.get('sc_player_active_tab')),
        })
        return shell

    # ------------------------------------------------------------------
    # Task 1588: the PROFILE language is the only source of truth
    # ------------------------------------------------------------------
    @staticmethod
    def _sc_profile_lang():
        """The frontend language serving the user's profile language
        (``res.users.lang``, or its nearest frontend sibling), or None when
        the frontend offers nothing close (then the request's language
        stands: never a redirect that cannot land)."""
        return request.env['ir.http'].get_nearest_lang(request.env.user.lang)

    @staticmethod
    def _sc_lang_url(url, lang_code):
        """``url`` (a local path + query) in ``lang_code``: any language
        prefix dropped, the frontend prefix of ``lang_code`` added when it is
        not the default language and the path is a multilang route — the URL
        the http_routing ``_match`` serves in that language WITHOUT a
        further language redirect (so no loop with the website's own)."""
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

    def _sc_profile_lang_guard(self):
        """Profile wins (owner decision 2026-10-12): a shell page served in
        another language than the user's profile one — a stale
        ``frontend_lang`` cookie, an ``/en/`` URL prefix — is redirected
        (GET/HEAD) to the same page in the profile language with the cookie
        reset to it. Other methods are aligned in place."""
        user = request.env.user
        if user._is_public():
            return
        target = self._sc_profile_lang()
        current = getattr(request, 'lang', None)
        if not target or not current or current.code == target:
            return
        if request.httprequest.method in ('GET', 'HEAD'):
            query = request.httprequest.query_string.decode()
            url = self._sc_lang_url(
                request.httprequest.path + ('?' + query if query else ''), target)
            response = request.redirect(url, code=303, local=True)
            response.set_cookie('frontend_lang', target)
            werkzeug.exceptions.abort(response)
        request.lang = request.env['res.lang']._get_data(code=target)
        request.update_context(lang=target)
        request.future_response.set_cookie('frontend_lang', target)

    @staticmethod
    def _sc_lang_options():
        """« Plus › Langue »: one entry per frontend language (FR / EN),
        the profile language pressed; empty with a single language."""
        frontend = request.env['res.lang']._get_frontend()
        if len(frontend) < 2:
            return []
        current = AppShellMixin._sc_profile_lang()
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
    def _sc_options(pairs):
        """[(key, label)] -> JSON-safe [[str(key), str(label)]]. Task 1608: a
        tags option may carry its group, (key, label, group_label, group_key)
        — kept, as strings."""
        return [[str(part) for part in option] for option in pairs]

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
                props[key] = str(value) if key in ('hint', 'placeholder', 'undoMessage', 'historyLabel') else value
        return json.dumps(props, default=str)

    @staticmethod
    def _sc_note_injury_options(patient):
        """Task 1665: the ONE injury list of the treatment-note forms (add
        AND edit, player page and clinic dossier): every injury of the player,
        the unresolved ones first (newest first), then the resolved ones
        suffixed « (résolue) ». ``[(id, label)]``; sudo: labels only, of the
        player's own injuries (the forms are gated by their routes)."""
        env = request.env
        injuries = patient.sudo().injury_ids.sorted(
            lambda i: (i.stage == 'resolved', -(i.id or 0)))
        options = []
        for injury in injuries:
            label = injury.diagnosis or injury.display_name
            if injury.stage == 'resolved':
                label = env._("%s (resolved)", label)
            options.append((injury.id, label))
        return options

    def _sc_note_edit_props(self, note):
        """Task 1587: the pencil edit fields of a treatment-note card — the
        text, the date and the linked injury. Task 1665: the same injury list
        as the add form (all the player's injuries, resolved ones last)."""
        env = request.env
        options = [('', env._("General note"))] + self._sc_note_injury_options(
            note.sudo().patient_id)
        return [
            self._sc_field_props(note, 'note', env._("Note"), 'textarea'),
            self._sc_field_props(note, 'date', env._("Date"), 'date'),
            self._sc_field_props(note, 'injury_id', env._("Injury"), 'select', options=options),
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
        for doc in env['sports.injury.document'].sudo().search(
                [('injury_id', 'in', injuries.ids)], order='create_date desc, id desc'):
            out.setdefault(doc.injury_id.id, []).append({
                'doc': doc,
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

    @staticmethod
    def _sc_form_props(target, label, input_type='tags', value='', **extra):
        """Task 1608 — JSON props of a FORM-mode sc_autosave_field: no
        autosave, no draft; the value goes to the enclosing form's hidden
        input ``target`` (its id), which the form posts as before."""
        props = {
            'mode': 'form',
            'target': target,
            'label': str(label),
            'inputType': input_type,
            'inputId': '%s_field' % target,
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
            return self._sc_shell_response(app_template, self._sc_app_values(values, app_template))
        return request.render(legacy_template, values)

    # ------------------------------------------------------------------
    # Task 1611: read fragments (see « Read fragments » above)
    # ------------------------------------------------------------------
    @staticmethod
    def _sc_fragment_keys():
        """The fragment keys a request asks for (``X-Sc-Fragments``), or None
        for a normal page request."""
        try:
            raw = request.httprequest.headers.get(SC_FRAGMENTS_HEADER)
        except RuntimeError:
            return None
        if raw is None:
            return None
        keys = []
        for key in raw.split(','):
            key = key.strip()
            if key and _SC_FRAGMENT_KEY_RE.match(key) and key not in keys:
                keys.append(key)
        return keys[:SC_FRAGMENTS_MAX]

    def _sc_shell_response(self, template, values):
        """A shell page: the page itself, or — asked with ``X-Sc-Fragments`` —
        the requested read fragments of the SAME render, as JSON (never
        cached)."""
        response = request.render(template, values)
        keys = self._sc_fragment_keys()
        if keys is None:
            return response
        found, title = sc_extract_fragments(response.render(), keys)
        sc_fill_moved_row_fragments(found, keys)
        response = request.make_json_response({
            'fragments': found,
            'missing': [key for key in keys if key not in found],
            'title': title,
            'rendered_at': values.get('sc_rendered_at') or sc_now_ms(),
        })
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Vary'] = SC_FRAGMENTS_HEADER
        return response

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
        return self._sc_shell_response('bemade_sports_clinic.sc_app_home',
                                       self._sc_app_values(values, 'sc_app_home'))

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
            clocks = self._sc_team_clocks(teams[:HOME_TEAMS_LIMIT])
            values.update({
                'sc_teams_count': len(teams),
                'sc_team_rows': [self._sc_team_row(team, clocks=clocks)
                                 for team in teams[:HOME_TEAMS_LIMIT]],
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
        return self._sc_shell_response('bemade_sports_clinic.sc_app_more',
                                       self._sc_app_values(values, 'sc_app_more'))

    # ------------------------------------------------------------------
    # /my/app/settings — « Paramètres » (task 1606: language, appearance,
    # account, security, classic portal — out of « Plus »; reached from the
    # user menu)
    # ------------------------------------------------------------------
    @http.route(['/my/app/settings'], type='http', auth='user', website=True)
    def sc_app_settings(self, **kw):
        if not self._sc_app_shell_active():
            return request.redirect('/my/home')
        values = self._prepare_portal_layout_values()
        values['page_name'] = 'sc_app_settings'
        return self._sc_shell_response('bemade_sports_clinic.sc_app_settings',
                                       self._sc_app_values(values, 'sc_app_settings'))

    # ------------------------------------------------------------------
    # /my/app/pref — the two self-service preferences, nothing else
    # ------------------------------------------------------------------
    @http.route(['/my/app/pref'], type='http', auth='user', website=True,
                methods=['POST'], multilang=False)
    def sc_app_pref(self, **post):
        """Set ``sc_theme`` on the CALLER's own record (task 1579: the
        navigation mode setting is gone) and/or ``lang`` (task 1588: one of
        the frontend languages — the profile language, mirrored in the
        ``frontend_lang`` cookie and the session; the redirect lands on the
        target page in that language).

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
        if not post or set(post) - set(PREF_FIELDS) - {PREF_LANG}:
            return request.make_json_response({'error': 'bad_request'}, status=400)
        for name, value in post.items():
            allowed = (request.env['res.lang']._get_frontend() if name == PREF_LANG
                       else PREF_FIELDS[name])
            if not value or value not in allowed:
                return request.make_json_response({'error': 'bad_request'}, status=400)
        vals = dict(post)
        for name in PREF_BOOLEANS:
            if name in vals:
                vals[name] = vals[name] == '1'
        user.write(vals)
        lang = post.get(PREF_LANG)
        if lang:
            # Task 1588: the session context too (the backend and the
            # http_routing fallback read it); the cookie below wins anyway.
            request.session.context = dict(request.session.context, lang=lang)
        accept = request.httprequest.headers.get('Accept', '')
        if 'application/json' in accept:
            response = request.make_json_response(
                {'sc_theme': self._sc_effective_theme(user), 'lang': user.lang})
        else:
            url = self._safe_return_url(redirect, '/my/app/settings')
            if lang:
                url = self._sc_lang_url(url, lang)
            response = request.redirect(url)
        if lang:
            response.set_cookie('frontend_lang', lang)
        return response

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

    @staticmethod
    def _sc_save_display(record, name):
        """The saved value as a reader sees it (owner review 2026-10-10: a
        card's read view updates in place after a save) — a name for a
        many2one, a label for a selection, a formatted date; '' when empty."""
        spec = SAVE_REGISTRY.get(record._name) or {}
        if spec.get('display'):
            shown = spec['display'](record, name)
            if shown is not None:
                return shown
        field = record._fields.get(name)
        if field is None:
            return ''
        value = record[name]
        if not value:
            return ''
        if field.type == 'many2one':
            # The plain name, as the select options show it (a province reads
            # « Quebec », not « Quebec (CA) »).
            value = value.sudo()
            return (value.name if 'name' in value._fields else value.display_name) or ''
        if field.type == 'selection':
            return dict(field._description_selection(record.env)).get(value, '')
        if field.type == 'date':
            return format_date(record.env, value)
        if field.type == 'datetime':
            return format_datetime(record.env, value)
        return str(value)

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
        """The 409 payload asking the client to confirm an identity
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
            'confirm_identity': True,
            'message': _("Correct this player's identity?"),
            'old': old,
            'new': new_text,
        }

    @staticmethod
    def _sc_save_proposal(spec, record, field):
        """Task 1603: the spec's follow-up proposal for this save (therapists
        only), or None. A builder failure never fails the save it follows."""
        if not spec.get('propose') or not (request.env.user._sc_app_roles() & _TP_ROLES):
            return None
        try:
            return spec['propose'](record, field) or None
        except Exception:  # noqa: BLE001 — a proposal is a convenience only
            _logger.exception("Follow-up proposal failed for %s.%s", record._name, field)
            return None

    def _sc_apply_changes(self, patient, changes):
        """Task 1603: write the changes of an applied proposal — each one
        re-validated (the proposal allowlist, the SAVE_REGISTRY role
        allowlist and check, the record belongs to ``patient``) and written
        by the spec's write hook (the normal save path: validation,
        tracking, history). Raises AccessError / ValidationError; the
        caller runs it in one savepoint (all or nothing). Returns the
        written (record, field) pairs."""
        done = []
        for change in changes:
            if not isinstance(change, dict):
                raise ValidationError(_("Invalid value."))
            model, field = change.get('model'), change.get('field')
            if field not in PROPOSAL_FIELDS.get(model, ()):
                raise AccessError(_("This change cannot be applied here."))
            spec = SAVE_REGISTRY.get(model)
            if not spec or not self._sc_save_allowed(spec, field):
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
            spec['write'](self, record, field, '' if value in (None, False) else str(value))
            done.append((record, field))
        return done

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
            return self._sc_save_json({'error': 'forbidden'}, 403)
        try:
            parsed = json.loads(changes or '')
            patient_id = int(patient_id)
        except (TypeError, ValueError):
            return self._sc_save_json({'error': 'bad_request'}, 400)
        if not isinstance(parsed, list) or not parsed or len(parsed) > PROPOSAL_MAX_CHANGES:
            return self._sc_save_json({'error': 'bad_request'}, 400)
        try:
            patient = self._check_access_to_patient(patient_id)
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
                    'value': self._sc_save_value(record, field),
                    'display': self._sc_save_display(record, field),
                    'write_date': fields.Datetime.to_string(record.write_date),
                })
                for pattern in sc_refresh_patterns(record._name, record, field):
                    if pattern not in refresh:
                        refresh.append(pattern)
            return self._sc_save_json({
                'ok': True,
                'saved': saved,
                'refresh': refresh,
                'saved_at': sc_now_ms(),
                'message': _("Changes applied."),
            })
        except (AccessError, MissingError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        except (UserError, ValidationError, ValueError) as exc:
            message = exc.args[0] if getattr(exc, 'args', None) else str(exc)
            return self._sc_save_json({'error': 'invalid', 'message': str(message)}, 400)

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
            return self._sc_save_json({'error': 'forbidden'}, 403)
        try:
            injury = self._check_access_to_injury(injury_id)
        except (AccessError, MissingError, UserError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        try:
            with request.env.cr.savepoint():
                run(injury)
                injury.flush_recordset()
        except (AccessError, MissingError):
            return self._sc_save_json({'error': 'forbidden'}, 403)
        except (UserError, ValidationError, ValueError) as exc:
            message = exc.args[0] if getattr(exc, 'args', None) else str(exc)
            return self._sc_save_json({'error': 'invalid', 'message': str(message)}, 400)
        injury.invalidate_recordset()
        model = injury._name
        payload = {
            'ok': True,
            'write_date': fields.Datetime.to_string(injury.write_date),
            'value': self._sc_save_value(injury, 'stage'),
            'display': self._sc_save_display(injury, 'stage'),
            'also': {name: {
                'value': self._sc_save_value(injury, name),
                'display': self._sc_save_display(injury, name),
            } for name in ('stage', 'resolution_date', 'predicted_resolution_date')},
            'refresh': sc_refresh_patterns(model, injury, 'stage'),
            'saved_at': sc_now_ms(),
            'live_counts': True,
            'message': message,
        }
        proposal = self._sc_save_proposal(SAVE_REGISTRY[model], injury, 'stage')
        if proposal:
            payload['propose'] = proposal
        return self._sc_save_json(payload)

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
        * 400 ``{error}`` — missing parameters or an invalid value;
        * 428 ``{confirm_identity, message, old, new}`` — task 1600: a portal
          user changes an existing first / last name or date of birth; nothing
          is written until the same save is re-posted with ``confirm=1``.
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
            # Owner review 2026-10-14: the stale-check and the 409 payload read
            # the field through sudo — the caller's role allowlist and the
            # spec's check passed above, and a group-restricted field (the
            # injury's internal notes) is not readable by a portal therapist
            # through the ORM after a sibling save changed the write_date.
            if current != write_date and not self._sc_field_unchanged(record.sudo(), field, old_value):
                return self._sc_save_json({
                    'conflict': True,
                    'current_value': self._sc_save_value(record.sudo(), field),
                    'current_write_date': current,
                    'by': record.sudo().write_uid.name or '',
                }, 409)
            if model == 'sports.patient':
                # Task 1639: the identity guard applies to everyone working
                # through the app (internal users included).
                record = record.with_context(sc_identity_guard=True)
            if model == 'sports.patient' and field in IDENTITY_FIELDS:
                # Task 1600: changing an existing name / date of birth is an
                # explicit, confirmed step (``confirm=1``, posted by the
                # field's confirm banner) — the model records it on the file.
                if kw.get('confirm') == '1':
                    record = record.with_context(**{IDENTITY_CONFIRM_KEY: True})
                else:
                    refusal = self._sc_identity_confirm_needed(record, field, value)
                    if refusal:
                        return self._sc_save_json(refusal, 428)
            extra = {}
            # A refused / invalid write leaves nothing behind (a hook may
            # write more than one field).
            # Task 1656: the teams before a player's teams save (a removal may
            # end the viewer's own access).
            teams_before = (record.sudo().team_ids
                            if model == 'sports.patient' and field == 'sc_team_ids' else None)
            with request.env.cr.savepoint():
                if spec.get('write'):
                    extra = spec['write'](self, record, field, value) or {}
                else:
                    if value == '' and record._fields[field].type not in _TEXT_TYPES:
                        value = False
                    record.write({field: value})
                record.flush_recordset()
            record.invalidate_recordset()
            if teams_before is not None:
                lost = self._sc_lost_access_payload(record, teams_before)
                if lost:
                    return self._sc_save_json(lost)
            payload = {
                'ok': True,
                'write_date': fields.Datetime.to_string(record.write_date),
                'value': self._sc_save_value(record, field),
                'display': self._sc_save_display(record, field),
            }
            # Other fields the write hook set along (e.g. an injury's
            # resolution date with « Resolved »), so the page updates them
            # in place: {field: {value, display}}.
            also = extra.pop('also_fields', None) or ()
            # Task 1594: and their fresh choices when they changed (a country
            # save answers the province choices of the new country).
            also_options = extra.pop('also_options', None) or {}
            # Task 1653: and whether they are locked now.
            also_disabled = extra.pop('also_disabled', None) or {}
            if also:
                payload['also'] = {name: {
                    'value': self._sc_save_value(record, name),
                    'display': self._sc_save_display(record, name),
                } for name in also}
                for name, options in also_options.items():
                    if name in payload['also']:
                        payload['also'][name]['options'] = AppShellMixin._sc_options(options)
                for name, disabled in also_disabled.items():
                    if name in payload['also']:
                        payload['also'][name]['disabled'] = bool(disabled)
            hint = spec['hint'](record, field) if spec.get('hint') else None
            if hint is not None:
                payload['hint'] = hint
            # Task 1611: the read fragments this save makes stale, the
            # server time of the save (the « back » check) and the live
            # counters to refresh.
            payload['refresh'] = sc_refresh_patterns(model, record, field)
            payload['saved_at'] = sc_now_ms()
            if spec.get('live_counts'):
                payload['live_counts'] = True
            # Task 1603: a follow-up proposal — never blocking (the field is
            # saved); the page shows it as a sheet (sc_proposal.js).
            # Task 1631: what the write hook knew before writing (e.g. an
            # injury's previous stage) reaches the proposal builder.
            propose_context = extra.pop('propose_context', None)
            proposal = self._sc_save_proposal(
                spec, record.with_context(**propose_context) if propose_context else record, field)
            if proposal:
                payload['propose'] = proposal
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
        return self._sc_shell_response('bemade_sports_clinic.sc_app_install',
                                       self._sc_app_values(values, 'sc_app_install'))


_validate_save_registry(SAVE_REGISTRY)
