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

Task 1397 adds, on the same page: the kiosk panel (open / copy / revoke the
per-clinic sign-in link + QR — assigned therapist or admin only, see
`_can_manage_kiosk`), the « to confirm » flag + Confirm action on rows the
kiosk matched on the name alone, and `/worklist/fragment` — the worklist
`<ul>` alone, same checks as the page, polled by the auto-refresh script.
"""
import logging
from urllib.parse import urlencode

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
        return on_clinic_teams.sorted('name'), (patients - on_clinic_teams).sorted('name')

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
    # #1397 — kiosk panel
    # ------------------------------------------------------------------
    @staticmethod
    def _can_manage_kiosk(event):
        """Open / revoke the kiosk: a therapist ASSIGNED to this clinic, or a
        system admin. Any TP may look at the clinic; handing out a public
        sign-in link for it is the assigned therapist's call."""
        user = request.env.user
        if user.has_group('base.group_system'):
            return True
        return user in event.sudo().assigned_staff_ids

    def _kiosk_values(self, event):
        """Template values for the kiosk panel (nothing when the user may not
        manage it). The QR is core's /report/barcode (public, reportlab), fed
        the absolute kiosk URL."""
        can_manage = self._can_manage_kiosk(event)
        values = {'kiosk_can_manage': can_manage, 'kiosk_open': False}
        if not can_manage:
            return values
        event_sudo = event.sudo()
        values['kiosk_open'] = event_sudo._kiosk_is_open()
        if values['kiosk_open']:
            url = event_sudo._kiosk_url()
            values['kiosk_url'] = url
            values['kiosk_qr_src'] = '/report/barcode/?' + urlencode({
                'barcode_type': 'QR', 'value': url, 'width': 240, 'height': 240,
            })
            values['kiosk_enabled_at'] = event_sudo.kiosk_enabled_at
        return values

    def _worklist_values(self, event, attendances, selected_patient):
        """The values the worklist sub-template needs — shared by the full
        page and by the fragment route so both render the SAME rows."""
        return {
            'event': event,
            'attendances': attendances,
            'accessible_patient_ids': self._accessible_patient_ids(attendances.patient_id),
            'selected_patient': selected_patient,
            'attendance_counts_line': _("Attendance: %s", self._attendance_counts_line(
                self._attendance_counts(attendances))) if attendances else False,
        }

    # ------------------------------------------------------------------
    # #1399 — attendance counts (portal gets COUNTS, never a patient list)
    # ------------------------------------------------------------------
    @staticmethod
    def _attendance_counts(attendances):
        """Disjoint counts for one clinic's rows: expected / arrived / seen /
        no-show, where no-show is the LIVE derivation (a row still Expected
        after the clinic ended), so the line is right the minute the clinic
        ends — the stored flag the backend report uses is the cron's job."""
        counts = {'expected': 0, 'arrived': 0, 'seen': 0, 'no_show': 0}
        for attendance in attendances:
            if attendance.state == 'expected' and attendance.is_no_show:
                counts['no_show'] += 1
            else:
                counts[attendance.state] += 1
        return counts

    @staticmethod
    def _attendance_counts_line(counts):
        """One translatable sentence for the counts (python-side on purpose:
        a QWeb text node mixed with four t-esc's would extract as four
        fragments no translator can act on)."""
        return _(
            "%(expected)s expected · %(arrived)s arrived · %(seen)s seen · %(no_show)s no-show",
            **counts)

    # ------------------------------------------------------------------
    # portal home counter
    # ------------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        # Portal-TP only: the card is a therapist surface, and any other portal
        # role would 403 on the sports.event count itself.
        if request.env.user.has_group(
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
            for group_event, count in Attendance._read_group(
                    [('event_id', 'in', clinics.ids)], ['event_id'], ['__count']):
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
        values.update({
            'selected_attendance': attendances.filtered(
                lambda a: a.patient_id == selected)[:1],
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
            'page_name': 'clinic_detail',
            'error': kw.get('error'),
            'success': kw.get('success'),
        })
        return request.render('bemade_sports_clinic.portal_clinic_detail', values)

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

    @staticmethod
    def _forbidden(error):
        """Render the standard portal 403 rather than a traceback."""
        response = request.render('http_routing.http_error', {
            'status_code': 403,
            'status_message': 'Forbidden',
            'error_message': str(error),
        })
        response.status_code = 403
        return response

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
    # #1397 — kiosk open / revoke
    # ------------------------------------------------------------------
    def _kiosk_route(self, event_id, action):
        self._check_clinic_access()
        try:
            event = self._get_clinic(event_id)
        except UserError:
            return request.redirect('/my/clinics?error=clinic_denied')
        if not self._can_manage_kiosk(event):
            return self._clinic_redirect(event, 'error=kiosk_denied', anchor='clinic-kiosk')
        if action == 'open':
            event.sudo()._kiosk_open()
            return self._clinic_redirect(event, 'success=kiosk_opened', anchor='clinic-kiosk')
        event.sudo()._kiosk_revoke()
        return self._clinic_redirect(event, 'success=kiosk_revoked', anchor='clinic-kiosk')

    @http.route(['/my/clinic/<int:event_id>/kiosk/open'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_clinic_kiosk_open(self, event_id, **post):
        """Open (or re-open) the sign-in kiosk for this clinic."""
        return self._kiosk_route(event_id, 'open')

    @http.route(['/my/clinic/<int:event_id>/kiosk/revoke'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_clinic_kiosk_revoke(self, event_id, **post):
        """Revoke every kiosk link issued for this clinic."""
        return self._kiosk_route(event_id, 'revoke')

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
