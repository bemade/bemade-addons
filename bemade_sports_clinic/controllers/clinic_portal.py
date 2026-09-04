"""Portal surface for clinics (task 1398) — `/my/clinics` and `/my/clinic/<id>`.

The therapist's working surface for a clinic: an ordered worklist of who is
here on the left, the selected patient's dossier on the right, and clinical
note capture docked at the bottom of that dossier. One page, no app switching
between "who is next" and "write down what I did".

Design points worth keeping:

* **Two INDEPENDENT filter axes on the list.** "mine" (assigned to me) is a
  boolean; time (today / upcoming / past / all) is a separate choice. They
  compose freely — mine OFF + past = every past clinic the therapist can see.
  Both default ON+today, which is the therapist's normal Monday morning.
* **Selection is server-rendered** (`?patient=<id>`), not JavaScript. The page
  works with JS disabled, survives a reload, and is linkable.
* **Note capture REUSES `/my/injury/note/add`.** There is no note-creation code
  in this file: the docked form posts to the existing treatment-note route with
  an extra `event_id`. A clinic note is a `sports.treatment.note` on the
  patient's file — NOT the `sports.quick.note` scratch pad (#1244), which is a
  private reminder and deliberately not a clinical record.

Security shape, identical on every route here:
  1. group check (portal or internal treatment professional),
  2. `_check_access_to_event` on the clinic,
  3. clinic-type check (a game is not a clinic),
  4. sudo() for the worklist read/write, with the target row re-verified to
     belong to THIS clinic — never inferred from the fact that the list query
     would not have shown it.

Task 1397 adds, on the same page: the kiosk panel (assigned therapist or
admin only, see `_can_manage_kiosk`), the « to confirm » flag + Confirm
action on rows the kiosk matched on the name alone, and `/worklist/fragment`
— the worklist `<ul>` alone, same checks as the page, polled by the
auto-refresh script. Task 1433 reversed the kiosk pairing: the panel is now
a pairing-code input plus the list of bound devices (« Dissocier » to
unbind) — the QR / signed link is gone; the iPad shows the code and the
therapist types it here.

Task 1418 adds the resolution of UNREGISTERED kiosk sign-ins (rows with no
patient, carrying the typed identity): `/attendance/<row>/link` (pick a file
— merged into that patient's existing row if any), `/attendance/<row>/
create_patient` (one click: the file is created from the typed data on a
clinic team the therapist staffs, then linked) and the existing `/remove`.
All three end on the dossier of the resolved patient. Every
`attendance.patient_id` read on these pages is guarded for the empty case.
"""
import logging

from psycopg2 import IntegrityError

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager

from .access_control_mixin import AccessControlMixin

_logger = logging.getLogger(__name__)

# Time axis values. Deliberately DISJOINT and exhaustive so the three named
# choices partition the timeline and nothing is unreachable.
CLINIC_TIME_FILTERS = ('today', 'upcoming', 'past', 'all')
DEFAULT_TIME_FILTER = 'today'


class ClinicPortal(CustomerPortal, AccessControlMixin):
    """Clinic list + the two-pane clinic worklist."""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_clinic_user():
        """Clinics are a therapist surface. Coaches are not clinic staff."""
        user = request.env.user
        return (
            user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
            or user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
            or user.has_group('base.group_system')
        )

    def _check_clinic_access(self):
        if not self._is_clinic_user():
            raise AccessError(_("Clinics are available to treatment professionals only."))

    def _get_clinic(self, event_id):
        """The event, proven accessible AND proven to be a clinic."""
        event = self._check_access_to_event(event_id)
        if event.sudo().event_type != 'clinic':
            raise MissingError(_("This event is not a clinic."))
        return event

    def _clinic_time_domain(self, time_filter):
        """Leaves for the time axis, in the user's timezone.

        today    : starts at some point today
        upcoming : starts after today ends
        past     : started before today began
        all      : no constraint
        """
        if time_filter == 'all':
            return []
        today = fields.Date.to_string(
            fields.Datetime.context_timestamp(
                request.env.user, fields.Datetime.now()).date())
        day_start = self._date_bound_to_utc(today, end_of_day=False)
        day_end = self._date_bound_to_utc(today, end_of_day=True)
        if time_filter == 'today':
            return [('date_start', '>=', day_start), ('date_start', '<=', day_end)]
        if time_filter == 'upcoming':
            return [('date_start', '>', day_end)]
        return [('date_start', '<', day_start)]  # past

    def _clinic_attendances(self, event):
        """The clinic's worklist, in order.

        sudo(): the worklist belongs to the CLINIC, so every therapist working
        it sees the same ordered list — otherwise two therapists on the same
        clinic would be reordering two different lists. Per-row dossier access
        is re-checked separately (see `_accessible_patient_ids`), exactly like
        /my/players does with its `accessible_ids`.
        """
        return request.env['sports.clinic.attendance'].sudo().search(
            [('event_id', '=', event.id)])

    @staticmethod
    def _accessible_patient_ids(patients):
        """Which of these patients this user may actually open a dossier for.

        Mirrors _check_access_to_patient: staff on one of the patient's teams,
        or a system admin. A row the user cannot open still shows on the
        worklist (it is the clinic's list, not theirs) but its dossier link is
        replaced by a "no access" hint rather than a link that would 403.
        """
        user = request.env.user
        if user.has_group('base.group_system'):
            return set(patients.ids)
        staffed = set(user.partner_id.team_staff_rel_ids.mapped('team_id').ids)
        return {p.id for p in patients if staffed.intersection(p.team_ids.ids)}

    def _addable_patients(self, event):
        """Patients the therapist may put on this worklist.

        Owner decision 2026-08-17: ad-hoc only, and only patients the therapist
        ALREADY has access to. No auto-population from the roster, and no
        special walk-in handling — a therapist who cannot reach a patient has
        working paths already (add the team to the clinic, add the patient to a
        served team, or create the patient), and patient self-service belongs
        to #1397.
        """
        staffed = request.env.user.partner_id.team_staff_rel_ids.mapped('team_id')
        if request.env.user.has_group('base.group_system'):
            patients = request.env['sports.patient'].sudo().search([])
        else:
            patients = request.env['sports.patient'].sudo().search(
                [('team_ids', 'in', staffed.ids or [0])])
        clinic_team_ids = set(event.sudo().team_ids.ids)
        # Patients from the clinic's own teams first: on a clinic for one team
        # that is the entire useful list, and it keeps the picker short.
        on_clinic_teams = patients.filtered(
            lambda p: clinic_team_ids.intersection(p.team_ids.ids))
        # Task 1414: « Last, First » order (accent / case insensitive) — the
        # order the picker shows, whatever res.partner.name sorts like.
        return (on_clinic_teams._portal_combo_sorted(),
                (patients - on_clinic_teams)._portal_combo_sorted())

    @staticmethod
    def _clinic_url(event, patient_id=None, query=None, anchor=None):
        """Detail URL preserving the selected patient (and an anchor).

        Every write route redirects through here so a state change, an add, a
        removal or a reorder never loses which patient the therapist was
        looking at, nor their place on the page.
        """
        url = '/my/clinic/%s' % event.id
        params = []
        if patient_id:
            params.append('patient=%s' % patient_id)
        if query:
            params.append(query)
        if params:
            url += '?' + '&'.join(params)
        if anchor:
            url += '#' + anchor
        return url

    def _clinic_redirect(self, event, query, patient_id=None, anchor='clinic-worklist'):
        return request.redirect(
            self._clinic_url(event, patient_id=patient_id, query=query, anchor=anchor))

    def _own_attendance(self, event, attendance_id):
        """A worklist row, re-proven to belong to THIS clinic.

        The write routes take an id straight off the wire; an id from another
        clinic must bounce off this and not off a rule that may not even apply
        (the rows are handled with sudo()).
        """
        attendance = request.env['sports.clinic.attendance'].sudo().browse(
            int(attendance_id))
        if not attendance.exists() or attendance.event_id != event:
            raise MissingError(_("This patient is not on this clinic's worklist."))
        return attendance

    # ------------------------------------------------------------------
    # #1397/#1433 — kiosk panel (reversed pairing)
    # ------------------------------------------------------------------
    @staticmethod
    def _can_manage_kiosk(event):
        """Pair / unbind a kiosk device: a therapist ASSIGNED to this clinic,
        or a system admin. Any TP may look at the clinic; activating a public
        sign-in surface for it is the assigned therapist's call."""
        user = request.env.user
        if user.has_group('base.group_system'):
            return True
        return user in event.sudo().assigned_staff_ids

    def _kiosk_values(self, event):
        """Template values for the kiosk panel (nothing when the user may not
        manage it): the currently bound devices — the card is a pairing-code
        input plus that list (#1433 replaced the QR/link panel)."""
        can_manage = self._can_manage_kiosk(event)
        values = {'kiosk_can_manage': can_manage,
                  'kiosk_devices': request.env['sports.clinic.kiosk.device']}
        if not can_manage:
            return values
        values['kiosk_devices'] = request.env[
            'sports.clinic.kiosk.device'].sudo().search([
                ('clinic_id', '=', event.id),
                ('bound_until', '>=', fields.Datetime.now()),
            ])
        return values

    def _worklist_values(self, event, attendances, selected_patient):
        """The values the worklist sub-template needs — shared by the full
        page and by the fragment route so both render the SAME rows.

        #1418: when an unregistered kiosk sign-in is on the list, the row's
        « Resolve » block needs the link picker (the same two groups as the
        add-patient combo) and the clinic teams the therapist may create a
        player on — computed here so the poll fragment renders them too."""
        values = {
            'event': event,
            'attendances': attendances,
            'accessible_patient_ids': self._accessible_patient_ids(attendances.patient_id),
            'selected_patient': selected_patient,
            'attendance_counts_line': _("Attendance: %s", self._attendance_counts_line(
                self._attendance_counts(attendances))) if attendances else False,
            'resolve_clinic_patients': request.env['sports.patient'],
            'resolve_other_patients': request.env['sports.patient'],
            'resolve_teams': request.env['sports.team'],
        }
        if any(not a.patient_id for a in attendances):
            on_clinic_teams, other_patients = self._addable_patients(event)
            values.update({
                'resolve_clinic_patients': on_clinic_teams,
                'resolve_other_patients': other_patients,
                'resolve_teams': self._creatable_teams(event),
            })
        return values

    @staticmethod
    def _creatable_teams(event):
        """The clinic's teams the current user may create a player on: the
        ones they staff (a system admin: all of them). A created player must
        be readable by its creator, and portal patient access is team-staff
        gated — so a team the therapist does not staff is not offered, and
        the route refuses it (#1418)."""
        teams = event.sudo().team_ids
        if request.env.user.has_group('base.group_system'):
            return teams
        staffed = request.env.user.partner_id.team_staff_rel_ids.mapped('team_id')
        return teams.filtered(lambda t: t in staffed)

    # ------------------------------------------------------------------
    # #1399 — attendance counts (portal gets COUNTS, never a patient list)
    # ------------------------------------------------------------------
    @staticmethod
    def _attendance_counts(attendances):
        """Disjoint counts for one clinic's rows: expected / arrived / seen /
        no-show, where no-show is the LIVE derivation (a row still Expected
        after the clinic ended), so the line is right the minute the clinic
        ends — the stored flag the backend report uses is the cron's job."""
        counts = {'expected': 0, 'arrived': 0, 'seen': 0, 'no_show': 0,
                  'unregistered': 0}
        for attendance in attendances:
            if not attendance.patient_id:
                # #1418: no patient file yet — its own bucket, never one of
                # the patient outcomes.
                counts['unregistered'] += 1
            elif attendance.state == 'expected' and attendance.is_no_show:
                counts['no_show'] += 1
            else:
                counts[attendance.state] += 1
        return counts

    @staticmethod
    def _attendance_counts_line(counts):
        """One translatable sentence for the counts (python-side on purpose:
        a QWeb text node mixed with four t-esc's would extract as four
        fragments no translator can act on)."""
        line = _(
            "%(expected)s expected · %(arrived)s arrived · %(seen)s seen · %(no_show)s no-show",
            **counts)
        if counts.get('unregistered'):
            # #1418: appended only when there is something to say.
            line += ' · ' + _("%(unregistered)s unregistered", **counts)
        return line

    # ------------------------------------------------------------------
    # portal home counter
    # ------------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        # Portal-TP only: the card is a therapist surface, and any other portal
        # role would 403 on the sports.event count itself.
        if 'clinics_count' in counters and request.env.user.has_group(
                'bemade_sports_clinic.group_portal_treatment_professional'):
            domain = self._prepare_events_domain('my')
            domain.append(('event_type', '=', 'clinic'))
            domain += self._clinic_time_domain('today')
            values['clinics_count'] = request.env['sports.event'].search_count(domain)
        return values

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------
    @http.route(['/my/clinics', '/my/clinics/page/<int:page>'], type='http',
                auth='user', website=True)
    def portal_my_clinics(self, page=1, mine=None, time_filter=None, team_id=None,
                          organization_id=None, filters_applied=None, **kw):
        """The therapist's clinics, defaulting to mine + today.

        `filters_applied` is the marker the filter form submits: an unchecked
        HTML checkbox posts nothing, so without it "mine unchecked" and "first
        visit" are indistinguishable and the toggle could never be turned off.
        """
        self._check_clinic_access()

        explicit = bool(filters_applied)
        if not explicit and mine is None and not time_filter:
            mine, time_filter = '1', DEFAULT_TIME_FILTER
        mine_on = bool(mine) and mine not in ('0', 'false', 'False')
        if time_filter not in CLINIC_TIME_FILTERS:
            time_filter = DEFAULT_TIME_FILTER

        # Axis 1: mine. _prepare_events_domain gives a portal therapist [] (they
        # can SEE every event); view_type='my' is what narrows to the clinics
        # they are assigned to.
        domain = self._prepare_events_domain('my' if mine_on else 'all')
        domain.append(('event_type', '=', 'clinic'))
        # Team / organization filters: the same helper the events list uses, so
        # they behave identically here.
        self._apply_event_filters(
            domain, team_id=team_id, organization_id=organization_id)
        # Axis 2: time.
        domain += self._clinic_time_domain(time_filter)

        Event = request.env['sports.event']
        total = Event.search_count(domain)
        pgr = pager(
            url='/my/clinics',
            url_args={
                'mine': '1' if mine_on else '0',
                'time_filter': time_filter,
                'team_id': team_id,
                'organization_id': organization_id,
                'filters_applied': '1',
            },
            total=total,
            page=page,
            step=self._items_per_page,
        )
        # Past clinics read newest-first; today/upcoming read next-first.
        order = 'date_start desc, name' if time_filter == 'past' else 'date_start asc, name'
        clinics = Event.search(
            domain, order=order, limit=self._items_per_page, offset=pgr['offset'])

        # One grouped count for the whole page rather than a query per card.
        # Clinics that have ENDED get the per-outcome counts line instead of
        # « N on the list » (#1399) — the list is history there, the counts are
        # the useful thing.
        counts = {}
        summaries = {}
        if clinics:
            Attendance = request.env['sports.clinic.attendance'].sudo()
            # #1418: unregistered kiosk sign-ins are not « on the list » —
            # they have no patient file yet (the ended-clinic summary line
            # still names them in their own bucket).
            for group_event, count in Attendance._read_group(
                    [('event_id', 'in', clinics.ids), ('patient_id', '!=', False)],
                    ['event_id'], ['__count']):
                counts[group_event.id] = count
            now = fields.Datetime.now()
            ended = clinics.sudo().filtered(
                lambda c: c.date_end and c.date_end < now and counts.get(c.id))
            if ended:
                rows = Attendance.search([('event_id', 'in', ended.ids)])
                for clinic in ended:
                    summaries[clinic.id] = self._attendance_counts_line(
                        self._attendance_counts(
                            rows.filtered(lambda r: r.event_id.id == clinic.id)))

        # Portal users cannot read other res.users, so resolve the assigned
        # therapists through sudo for display only (mirrors the events list).
        assigned_by_clinic = {ev.id: ev.assigned_staff_ids for ev in clinics.sudo()}

        return request.render('bemade_sports_clinic.portal_my_clinics', {
            'clinics': clinics,
            'clinics_count': total,
            'attendance_counts': counts,
            'attendance_summaries': summaries,
            'assigned_by_clinic': assigned_by_clinic,
            'pager': pgr,
            'page_name': 'clinics',
            # current filter values
            'mine': mine_on,
            'time_filter': time_filter,
            'team_id': int(team_id) if team_id else None,
            'organization_id': int(organization_id) if organization_id else None,
            # filter options
            'teams': self._get_all_teams(),
            'organizations': self._get_all_organizations(),
            'error': kw.get('error'),
            'success': kw.get('success'),
        })

    # ------------------------------------------------------------------
    # detail (two-pane)
    # ------------------------------------------------------------------
    @http.route(['/my/clinic/<int:event_id>'], type='http', auth='user', website=True)
    def portal_clinic_detail(self, event_id, patient=None, **kw):
        """Worklist left, dossier right, note capture docked under the dossier."""
        self._check_clinic_access()
        try:
            event = self._get_clinic(event_id)
        except UserError as error:
            return self._forbidden(error)

        attendances = self._clinic_attendances(event)
        accessible_ids = self._accessible_patient_ids(attendances.patient_id)

        # Selected patient: explicit ?patient=, else the first row the user can
        # actually open, so the right pane is never pointlessly empty.
        selected = request.env['sports.patient']
        selected_id = None
        try:
            selected_id = int(patient) if patient else None
        except (TypeError, ValueError):
            selected_id = None
        if selected_id is None:
            openable = attendances.filtered(
                lambda a: a.patient_id.id in accessible_ids)
            selected_id = openable[:1].patient_id.id or None
        if selected_id and selected_id in accessible_ids:
            # Re-verify server-side rather than trusting the query string.
            try:
                selected = self._check_access_to_patient(selected_id)
            except UserError:
                selected = request.env['sports.patient']

        injuries = request.env['sports.patient.injury']
        notes = request.env['sports.treatment.note']
        if selected:
            injuries = selected.injury_ids.filtered(lambda i: i.stage == 'active')
            notes = request.env['sports.treatment.note'].sudo().search(
                [('patient_id', '=', selected.id)], order='date desc, id desc',
                limit=20)

        on_clinic_teams, other_patients = self._addable_patients(event)
        already = set(attendances.patient_id.ids)

        values = self._worklist_values(event, attendances, selected)
        values.update(self._kiosk_values(event))
        values.update(self._dossier_edit_values(event, selected, injuries, kw))
        values.update({
            'selected_attendance': attendances.filtered(
                lambda a: selected and a.patient_id == selected)[:1],
            'active_injuries': injuries,
            'treatment_notes': notes,
            'addable_clinic_patients': on_clinic_teams.filtered(
                lambda p: p.id not in already),
            'addable_other_patients': other_patients.filtered(
                lambda p: p.id not in already),
            'attendance_states': dict(
                request.env['sports.clinic.attendance']._fields['state'].selection),
            'note_return_url': self._clinic_url(
                event, patient_id=selected.id if selected else None,
                anchor='clinic-notes'),
            # Task 1413: « Linked injury » select default — the single active
            # injury when there is exactly one, else « General note »; which
            # notes the current user may edit (author / clinic admin); and the
            # note whose edit form bounced (its form re-opens with the error).
            'note_default_injury_id': injuries.id if len(injuries) == 1 else False,
            'editable_note_ids': {
                n.id for n in notes if n._can_portal_edit(request.env.user)},
            'note_error_id': self._int_or_none(kw.get('note_id')),
            # Task 1410: the dossier's out-links (« Full file », active injuries)
            # carry the clinic as navigation context — plus the team when the
            # clinic serves exactly one (the player page re-validates both).
            'dossier_ctx_qs': '&clinic_id=%s' % event.id + (
                '&team_id=%s' % event.team_ids.id if len(event.team_ids) == 1 else ''),
            'page_name': 'clinic_detail',
            'error': kw.get('error'),
            'success': kw.get('success'),
        })
        return request.render('bemade_sports_clinic.portal_clinic_detail', values)

    def _dossier_edit_values(self, event, selected, injuries, kw):
        """Task 1411 — what the dossier's inline forms need: the TP guard for
        internal notes / player notes, per-injury and patient return URLs
        (back to THIS clinic, same patient, card in view), the translated
        status selections, and the values the status form shows — the refused
        pair when the last save bounced with error=invalid_status_combo."""
        Patient = request.env['sports.patient']
        Injury = request.env['sports.patient.injury']
        env = request.env
        match_sel = Patient._fields['match_status']._description_selection(env)
        practice_sel = Patient._fields['practice_status']._description_selection(env)
        form_values = {
            'match_status': selected.match_status if selected else False,
            'practice_status': selected.practice_status if selected else False,
        }
        if kw.get('error') == 'invalid_status_combo':
            for fname, sel in (('match_status', match_sel), ('practice_status', practice_sel)):
                attempted = kw.get(fname)
                if attempted in dict(sel):
                    form_values[fname] = attempted
        return {
            'is_treatment_prof': self._is_treatment_professional(),
            'injury_return_urls': {
                inj.id: self._clinic_return_url(event, selected.id, anchor='clinic-injury-%s' % inj.id)
                for inj in injuries},
            'injury_stage_labels': dict(Injury._fields['stage']._description_selection(env)),
            'quick_action_url': '/my/player/%s/quick' % selected.id if selected else '',
            'quick_return_url': self._clinic_return_url(event, selected.id) if selected else '',
            'match_status_selection': match_sel,
            'practice_status_selection': practice_sel,
            'status_form_values': form_values,
        }

    @http.route(['/my/clinic/<int:event_id>/worklist/fragment'], type='http',
                auth='user', website=True, methods=['GET'])
    def portal_clinic_worklist_fragment(self, event_id, patient=None, **kw):
        """The worklist `<ul>` alone, for the auto-refresh poll (#1397).

        Same checks as the page (group, event access, clinic type) — a coach
        403s here exactly like on /my/clinic/<id>. `?patient=` keeps the
        selected highlight. Never cached.
        """
        self._check_clinic_access()
        try:
            event = self._get_clinic(event_id)
        except UserError as error:
            return self._forbidden(error)
        attendances = self._clinic_attendances(event)
        selected = request.env['sports.patient']
        try:
            selected_id = int(patient) if patient else None
        except (TypeError, ValueError):
            selected_id = None
        if selected_id:
            selected = attendances.patient_id.filtered(lambda p: p.id == selected_id)
        values = self._worklist_values(event, attendances, selected)
        values['request'] = request
        html = request.env['ir.ui.view']._render_template(
            'bemade_sports_clinic.portal_clinic_worklist', values)
        return request.make_response(html, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store'),
        ])

    # _forbidden (the standard portal 403 page) moved to AccessControlMixin
    # in task 1412 so the injury fragment routes render the same page.

    # ------------------------------------------------------------------
    # write routes
    # ------------------------------------------------------------------
    @http.route(['/my/clinic/<int:event_id>/attendance/add'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_clinic_attendance_add(self, event_id, **post):
        """Put a patient on the worklist. Ad-hoc only, access-gated."""
        self._check_clinic_access()
        try:
            event = self._get_clinic(event_id)
        except UserError:
            return request.redirect('/my/clinics?error=clinic_denied')

        raw = (post.get('patient_id') or '').strip()
        if not raw:
            return self._clinic_redirect(event, 'error=no_patient')
        try:
            patient = self._check_access_to_patient(int(raw))
        except (ValueError, UserError):
            # A patient outside the therapist's access is refused, not silently
            # dropped — otherwise the add just appears to do nothing.
            return self._clinic_redirect(event, 'error=patient_denied')

        Attendance = request.env['sports.clinic.attendance'].sudo()
        vals = {'event_id': event.id, 'patient_id': patient.id}
        try:
            # savepoint: the unique (event_id, patient_id) constraint must
            # surface as a flash, not a poisoned cursor and a 500.
            with request.env.cr.savepoint():
                Attendance.create(vals)
        except (IntegrityError, ValidationError):
            return self._clinic_redirect(
                event, 'error=duplicate_patient', patient_id=patient.id)
        return self._clinic_redirect(
            event, 'success=patient_added', patient_id=patient.id)

    @http.route(['/my/clinic/<int:event_id>/attendance/<int:attendance_id>/remove'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_clinic_attendance_remove(self, event_id, attendance_id, **post):
        """Take a patient off the worklist. The patient record is untouched."""
        self._check_clinic_access()
        try:
            event = self._get_clinic(event_id)
            attendance = self._own_attendance(event, attendance_id)
        except UserError:
            return request.redirect('/my/clinics?error=clinic_denied')
        removed_patient_id = attendance.patient_id.id
        if not attendance.patient_id:
            # #1418: the typed identity goes with the row; ids-only audit.
            attendance._audit_unregistered('remove')
        attendance.unlink()
        # Do not keep pointing the dossier at someone no longer on the list.
        keep = post.get('patient')
        try:
            keep = int(keep) if keep else None
        except (TypeError, ValueError):
            keep = None
        if keep == removed_patient_id:
            keep = None
        return self._clinic_redirect(event, 'success=patient_removed', patient_id=keep)

    @http.route(['/my/clinic/<int:event_id>/attendance/<int:attendance_id>/state'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_clinic_attendance_state(self, event_id, attendance_id, **post):
        """Advance (or correct) a row: Expected -> Arrived -> Seen.

        The arrived_at / seen_at stamps are the MODEL's job, not this route's,
        so the #1397 kiosk gets them for free when it writes the same field.
        """
        self._check_clinic_access()
        try:
            event = self._get_clinic(event_id)
            attendance = self._own_attendance(event, attendance_id)
        except UserError:
            return request.redirect('/my/clinics?error=clinic_denied')

        state = post.get('state')
        valid = dict(attendance._fields['state'].selection)
        if state not in valid:
            return self._clinic_redirect(event, 'error=bad_state',
                                         patient_id=attendance.patient_id.id)
        if not attendance.patient_id:
            # #1418: an unregistered sign-in has no lifecycle of its own —
            # it is Arrived by definition until linked, created or removed.
            return self._clinic_redirect(event, 'error=unregistered_row',
                                         anchor='attendance-%s' % attendance.id)
        attendance.write({'state': state})
        return self._clinic_redirect(event, 'success=state_updated',
                                     patient_id=attendance.patient_id.id,
                                     anchor='attendance-%s' % attendance.id)

    @http.route(['/my/clinic/<int:event_id>/attendance/<int:attendance_id>/confirm'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_clinic_attendance_confirm(self, event_id, attendance_id, **post):
        """Therapist vouches for a name-only kiosk match (#1397)."""
        self._check_clinic_access()
        try:
            event = self._get_clinic(event_id)
            attendance = self._own_attendance(event, attendance_id)
        except UserError:
            return request.redirect('/my/clinics?error=clinic_denied')
        attendance.action_confirm()
        return self._clinic_redirect(event, 'success=identity_confirmed',
                                     patient_id=attendance.patient_id.id,
                                     anchor='attendance-%s' % attendance.id)

    # ------------------------------------------------------------------
    # #1418 — resolve an unregistered kiosk sign-in: link / create
    # ------------------------------------------------------------------
    def _unregistered_row(self, event_id, attendance_id):
        """(event, row) for the resolve routes — the row re-proven to belong
        to this clinic AND to be unregistered (a linked row bounces with a
        flash, never a traceback)."""
        self._check_clinic_access()
        event = self._get_clinic(event_id)
        attendance = self._own_attendance(event, attendance_id)
        return event, attendance

    @http.route(['/my/clinic/<int:event_id>/attendance/<int:attendance_id>/link'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_clinic_attendance_link(self, event_id, attendance_id, **post):
        """Link an unregistered kiosk sign-in to an existing patient file.

        The patient must be one the therapist may open (same gate as the
        add-patient route); if that patient already has a row on the clinic
        the two are merged (the model keeps the earlier arrival). Ends on the
        patient's dossier.
        """
        try:
            event, attendance = self._unregistered_row(event_id, attendance_id)
        except UserError:
            return request.redirect('/my/clinics?error=clinic_denied')
        if attendance.patient_id:
            return self._clinic_redirect(event, 'error=unregistered_row',
                                         patient_id=attendance.patient_id.id)
        raw = (post.get('patient_id') or '').strip()
        if not raw:
            return self._clinic_redirect(event, 'error=no_patient',
                                         anchor='attendance-%s' % attendance.id)
        try:
            patient = self._check_access_to_patient(int(raw))
        except (ValueError, UserError):
            return self._clinic_redirect(event, 'error=patient_denied',
                                         anchor='attendance-%s' % attendance.id)
        row = attendance.action_link_patient(patient)
        return self._clinic_redirect(event, 'success=signin_linked',
                                     patient_id=row.patient_id.id,
                                     anchor='clinic-dossier')

    @http.route(['/my/clinic/<int:event_id>/attendance/<int:attendance_id>/create_patient'],
                type='http', auth='user', website=True, methods=['POST'])
    def portal_clinic_attendance_create_patient(self, event_id, attendance_id, **post):
        """One click: create the player from the typed identity on a clinic
        team the therapist staffs (implicit when the clinic has one; posted
        `team_id` otherwise), link the row, open the new dossier.

        A team the therapist does not staff — or that is not one of the
        clinic's — is refused with a 403 page: the creator must be able to
        read the file they just created.
        """
        try:
            event, attendance = self._unregistered_row(event_id, attendance_id)
        except UserError:
            return request.redirect('/my/clinics?error=clinic_denied')
        if attendance.patient_id:
            return self._clinic_redirect(event, 'error=unregistered_row',
                                         patient_id=attendance.patient_id.id)
        allowed = self._creatable_teams(event)
        clinic_teams = event.sudo().team_ids
        raw_team = (post.get('team_id') or '').strip()
        if raw_team:
            team_id = self._int_or_none(raw_team)
            team = clinic_teams.filtered(lambda t: t.id == team_id)
            if not team:
                return self._forbidden(AccessError(_(
                    "The team must be one of this clinic's teams.")))
            if team not in allowed:
                return self._forbidden(AccessError(_(
                    "You can only create a player on a team you are staff on.")))
        elif len(clinic_teams) == 1 and clinic_teams in allowed:
            team = clinic_teams
        elif len(clinic_teams) == 1:
            return self._forbidden(AccessError(_(
                "You can only create a player on a team you are staff on.")))
        else:
            return self._clinic_redirect(event, 'error=no_team',
                                         anchor='attendance-%s' % attendance.id)
        row, patient = attendance.action_create_patient(team)
        return self._clinic_redirect(event, 'success=signin_patient_created',
                                     patient_id=patient.id, anchor='clinic-dossier')

    # ------------------------------------------------------------------
    # #1433 — kiosk pair / unbind (reversed pairing)
    # ------------------------------------------------------------------
    def _kiosk_gate(self, event_id):
        """The shared gate of the kiosk write routes: clinic user, accessible
        clinic, may manage its kiosk. Returns (event, error_response)."""
        self._check_clinic_access()
        try:
            event = self._get_clinic(event_id)
        except UserError:
            return None, request.redirect('/my/clinics?error=clinic_denied')
        if not self._can_manage_kiosk(event):
            return None, self._clinic_redirect(
                event, 'error=kiosk_denied', anchor='clinic-kiosk')
        return event, None

    @http.route(['/my/clinic/<int:event_id>/kiosk/pair'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_clinic_kiosk_pair(self, event_id, **post):
        """Bind the kiosk device showing this pairing code to this clinic.
        The device transitions by itself (it polls); nobody touches the iPad.
        sudo() after the gate — the existing kiosk-panel pattern."""
        event, error = self._kiosk_gate(event_id)
        if error:
            return error
        device = request.env['sports.clinic.kiosk.device']._pair(
            post.get('code'), event.sudo())
        if not device:
            return self._clinic_redirect(event, 'error=kiosk_code',
                                         anchor='clinic-kiosk')
        return self._clinic_redirect(event, 'success=kiosk_paired',
                                     anchor='clinic-kiosk')

    @http.route(['/my/clinic/<int:event_id>/kiosk/unbind'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_clinic_kiosk_unbind(self, event_id, **post):
        """« Dissocier » one bound device: it falls back to its pairing
        screen. The device is re-proven to belong to THIS clinic."""
        event, error = self._kiosk_gate(event_id)
        if error:
            return error
        try:
            device_id = int(post.get('device_id') or 0)
        except (TypeError, ValueError):
            device_id = 0
        device = request.env['sports.clinic.kiosk.device'].sudo().browse(
            device_id).exists()
        if not device or device.clinic_id != event.sudo():
            return self._clinic_redirect(event, 'error=kiosk_device',
                                         anchor='clinic-kiosk')
        device._unbind()
        return self._clinic_redirect(event, 'success=kiosk_unbound',
                                     anchor='clinic-kiosk')

    @http.route(['/my/clinic/<int:event_id>/attendance/reorder'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_clinic_attendance_reorder(self, event_id, **post):
        """Persist a new worklist order.

        ONE endpoint, two callers:
        * drag posts `order` — the full id order, once, after the drop (never a
          POST per intermediate move);
        * the up/down buttons post `attendance_id` + `direction`, which is the
          keyboard-accessible path, the no-JS path, and the only reorder path
          on a phone (desktop HTML5 drag does nothing on touch, by decision).
        """
        self._check_clinic_access()
        try:
            event = self._get_clinic(event_id)
        except UserError:
            return request.redirect('/my/clinics?error=clinic_denied')
        worklist = self._clinic_attendances(event)

        keep = post.get('patient')
        try:
            keep = int(keep) if keep else None
        except (TypeError, ValueError):
            keep = None

        raw_order = (post.get('order') or '').strip()
        if raw_order:
            ordered_ids = []
            for chunk in raw_order.split(','):
                chunk = chunk.strip()
                if chunk.isdigit():
                    ordered_ids.append(int(chunk))
            if not ordered_ids:
                return self._clinic_redirect(event, 'error=bad_order', patient_id=keep)
            # _set_worklist_order ignores ids outside this clinic's worklist.
            worklist._set_worklist_order(ordered_ids)
            return self._clinic_redirect(event, 'success=order_saved', patient_id=keep)

        attendance_id = post.get('attendance_id')
        direction = post.get('direction')
        if not attendance_id or direction not in ('up', 'down'):
            return self._clinic_redirect(event, 'error=bad_order', patient_id=keep)
        try:
            attendance = self._own_attendance(event, attendance_id)
        except UserError:
            return self._clinic_redirect(event, 'error=bad_order', patient_id=keep)
        attendance._move_in_worklist(direction)
        return self._clinic_redirect(event, 'success=order_saved', patient_id=keep,
                                     anchor='attendance-%s' % attendance.id)
