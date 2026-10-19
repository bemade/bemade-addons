#
#    Bemade Inc.
#
#    Copyright (C) October 2023 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the Odoo Proprietary License v1.0 (OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the Software
#    or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#

from odoo import http, _, fields
from odoo.exceptions import UserError, AccessError, MissingError
from odoo.http import request
from odoo.tools import format_date

from ..models import sc_app_nav
from datetime import datetime, time
import time as systime
import logging
import pytz

_logger = logging.getLogger(__name__)


class AccessControlMixin:
    """
    Mixin class providing common access control methods for portal controllers.
    
    This centralizes access control logic to avoid duplication across multiple controllers
    and ensures consistent security checks throughout the portal interface.
    """

    # ------------------------------------------------------------------
    # Shared portal helpers (consolidated here after the dead-route audit;
    # previously duplicated across events_portal / team_staff_portal /
    # timesheets_portal where only one copy won by import order).
    # ------------------------------------------------------------------

    def _parse_portal_datetime(self, val):
        """Parse a datetime-local input (YYYY-MM-DDTHH:MM[:SS]) from the portal
        as user-local time and convert to a UTC string for fields.Datetime.
        Returns False if empty; returns the raw value if it can't be parsed.
        """
        if not val:
            return False
        dt = None
        try:
            if 'T' in val:
                try:
                    dt = datetime.strptime(val, '%Y-%m-%dT%H:%M')
                except ValueError:
                    dt = datetime.strptime(val, '%Y-%m-%dT%H:%M:%S')
            else:
                try:
                    dt = datetime.strptime(val, '%Y-%m-%d %H:%M')
                except ValueError:
                    dt = datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # Fallback: let the ORM try to coerce whatever string was provided.
            return val

        user_tz = http.request.env.tz
        local_dt = user_tz.localize(dt)
        utc_dt = local_dt.astimezone(pytz.UTC)
        return fields.Datetime.to_string(utc_dt)

    def _prepare_events_domain(self, view_type='all', include_cancelled=False):
        """Prepare domain for sports events based on user access.

        Cancelled events are excluded by default so the portal list and
        calendar mirror the internal views (task 1235). Callers pass
        include_cancelled=True (driven by an explicit ``show_cancelled``
        toggle) to surface them again.
        """
        user = http.request.env.user
        partner = user.partner_id

        # Therapists see all events; coaches only their teams' events.
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
            user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')

        if is_therapist:
            base_domain = []
        elif is_coach:
            team_staff_rels = partner.team_staff_rel_ids
            team_ids = team_staff_rels.mapped('team_id.id')
            base_domain = [('team_ids', 'in', team_ids or [0])]
        else:
            base_domain = [('id', '=', 0)]  # No results

        # View-specific filters
        if view_type == 'my':
            base_domain.append(('assigned_staff_ids', 'in', [user.id]))
        elif view_type == 'unassigned':
            base_domain.append(('assigned_staff_ids', '=', False))
        elif view_type == 'missing_timesheets':
            shared_users = http.request.env['res.users'].search([('partner_id', '=', partner.id)])
            shared_user_ids = shared_users.ids or [user.id]
            base_domain.extend([
                ('assigned_staff_ids', 'in', shared_user_ids),
                '!',
                ('timesheet_ids.user_id', 'in', shared_user_ids),
            ])
        # 'all' view uses base domain only

        # Drop cancelled events from the default surfaces unless explicitly
        # requested. Appended last; the implicit-AND combine is correct even
        # for the missing_timesheets branch (which uses a '!' prefix operator).
        if not include_cancelled:
            base_domain.append(('state', '!=', 'cancelled'))
        return base_domain

    def _date_bound_to_utc(self, date_str, end_of_day=False):
        """Convert a YYYY-MM-DD date filter (interpreted in the user's tz)
        into a naive-UTC datetime string for comparison against the
        UTC-stored date_start. end_of_day pins to 23:59:59.999999."""
        if not date_str:
            return None
        try:
            d = fields.Date.from_string(date_str)
        except Exception:
            return None
        user_tz = http.request.env.tz
        t = time.max if end_of_day else time.min
        local_dt = user_tz.localize(datetime.combine(d, t))
        utc_dt = local_dt.astimezone(pytz.UTC)
        return fields.Datetime.to_string(utc_dt)

    def _apply_event_filters(self, domain, team_id=None, organization_id=None,
                             assigned_user_id=None, date_from=None, date_to=None,
                             event_type=None, search=None):
        """Append the portal list-style filter leaves (team / organization /
        assigned professional / date range / event type / free-text search)
        to an events domain.

        Shared by the list view and the calendar JSON feed so both honor an
        identical set of filters (task 1591 added ``event_type`` and
        ``search``; ``event_type`` must already be a known selection key).
        Mutates and returns ``domain``.
        """
        if event_type:
            domain.append(('event_type', '=', event_type))
        if search:
            domain.extend([
                '|', '|', '|',
                ('name', 'ilike', search),
                ('description', 'ilike', search),
                ('team_ids.name', 'ilike', search),
                ('venue_id.name', 'ilike', search),
            ])
        if team_id:
            domain.append(('team_ids', 'in', [int(team_id)]))
        if organization_id:
            domain.append(('partner_id', '=', int(organization_id)))
        if assigned_user_id:
            domain.append(('assigned_staff_ids', 'in', [int(assigned_user_id)]))
        if date_from:
            dt_utc = self._date_bound_to_utc(date_from, end_of_day=False)
            if dt_utc:
                domain.append(('date_start', '>=', dt_utc))
        if date_to:
            dt_utc = self._date_bound_to_utc(date_to, end_of_day=True)
            if dt_utc:
                domain.append(('date_start', '<=', dt_utc))
        return domain

    def _get_accessible_teams(self):
        """Teams accessible to the current user, name order.

        Task 1577 (owner decision 2026-09-28), always explicit — never a bare
        ``search([])`` left to the record rules:

        * a clinic administrator (or system admin) → EVERY team, the teams
          they staff listed first;
        * a treatment professional (portal or internal) → the teams they
          staff (the same set their team record rule already allows);
        * anyone else (coaches) → the teams they staff, through their staff
          rows (unchanged).
        """
        user = http.request.env.user
        partner = user.partner_id
        Teams = http.request.env['sports.team']
        if self._is_clinic_admin():
            return self._staffed_first(Teams.search([], order='name'))
        if self._is_treatment_professional():
            teams = Teams.search([('staff_ids.user_ids', 'in', user.id)])
        else:
            team_staff_rels = partner.team_staff_rel_ids
            team_ids = team_staff_rels.mapped('team_id.id')
            teams = Teams.browse(team_ids)
        return teams.sorted('name')

    @staticmethod
    def _staffed_first(teams, staffed=None):
        """``teams`` with the ones the current user staffs first, keeping the
        incoming order inside each half (task 1577: a clinic admin sees every
        team, their own on top). ``staffed``: the staffed recordset when the
        caller already has it; else the user's staff rows decide."""
        if staffed is None:
            staffed = http.request.env.user.partner_id.sudo().team_staff_rel_ids.team_id
        staffed_ids = set(staffed.ids)
        return teams.sorted(key=lambda team: team.id not in staffed_ids)

    def _team_targets(self):
        """Teams a player form may assign / link a player to (create player,
        edit player, add/link page): the teams the user staffs, name order —
        EVERY team for a clinic administrator, staffed first (task 1577).
        Used both for the options AND to filter the posted ids."""
        env = request.env
        staffed = env['sports.team'].search([
            ('id', 'in', env['sports.team.staff'].search([
                ('partner_id', '=', env.user.partner_id.id)
            ]).mapped('team_id').ids)
        ], order='name')
        return self._admin_or_staffed_teams(staffed)

    # ------------------------------------------------------------------
    # Activity permissions (task 1589, owner decision 2026-10-12) — ONE
    # place for who may open / act on an activity in the portal:
    #   * clinic / system administrator: everything;
    #   * a coach (portal coach who is not a therapist): only the
    #     activities assigned to them OR created by them, within their team
    #     scope — they never see the others (matches the coach record rule
    #     ``mail_activity_portal_team_coach_rule``);
    #   * everyone else (therapists, …): the assignee, or staff of the
    #     related patient / team / event's teams.
    # « Act » = edit (pencil / edit page), complete, cancel, reschedule,
    # reassign. Writes run with sudo() only AFTER this check.
    # ------------------------------------------------------------------

    def _activity_coach_only(self):
        """A portal coach who is neither a therapist (portal or internal)
        nor a clinic / system administrator (task 1589)."""
        user = http.request.env.user
        return (
            user.has_group('bemade_sports_clinic.group_portal_team_coach')
            and not self._is_tp_or_system()
            and not self._is_clinic_admin())

    def _activity_in_scope(self, activity):
        """Is ``activity``'s related patient / team / event in the viewer's
        team scope (``_activity_scope_teams``)? sudo(): only to read the
        related record's teams for the comparison."""
        activity = activity.sudo()
        if activity.res_model not in ('sports.patient', 'sports.team', 'sports.event'):
            return False
        record = http.request.env[activity.res_model].sudo().browse(activity.res_id)
        if not activity.res_id or not record.exists():
            return False
        teams = self._activity_scope_teams()
        if activity.res_model == 'sports.team':
            return bool(teams & record)
        return bool(teams.ids and set(teams.ids) & set(record.team_ids.ids))

    def _activity_act_access(self, activity):
        """May the current user ACT on ``activity`` (edit, complete, cancel,
        reschedule, reassign)? See the rules above (task 1589)."""
        env = http.request.env
        activity = activity.sudo()
        if not activity.exists():
            return False
        if self._is_clinic_admin():
            return True
        user = env.user
        if self._activity_coach_only():
            return ((activity.user_id == user or activity.create_uid == user)
                    and self._activity_in_scope(activity))
        if activity.user_id == user:
            return True
        return self._activity_in_scope(activity)

    def _activity_view_access(self, activity):
        """May the current user OPEN ``activity`` — the detail page and its
        attachment downloads (task 1586). Task 1589: whoever may act on it
        may open it, and nobody else (a coach never opens another's
        activity)."""
        return self._activity_act_access(activity)

    @staticmethod
    def _activity_attachments(activity):
        """The attachments of ``activity`` the portal lists and serves (task
        1586): those attached to it (res_model/res_id) plus its
        ``attachment_ids``. sudo(): the caller's _activity_view_access is the
        authorization — coaches have no ir.attachment read on
        mail.activity."""
        Attachment = http.request.env['ir.attachment'].sudo()
        attached = Attachment.search([
            ('res_model', '=', 'mail.activity'),
            ('res_id', '=', activity.id),
        ])
        return attached | activity.sudo().attachment_ids

    # Task 1595: the record(s) an activity row / detail links to. Kind →
    # (portal URL pattern, sc_icon key).
    _SC_ACTIVITY_RELATED_KINDS = {
        'sports.patient': ('/my/player?player_id=%s', 'players'),
        'sports.team': ('/my/team?team_id=%s', 'teams'),
        'sports.event': ('/my/event/%s', 'calendar'),
        'sports.patient.injury': ('/my/injury/edit?injury_id=%s', 'injury'),
    }

    def _sc_activity_record_link(self, record):
        """``{'model', 'id', 'name', 'url', 'icon'}`` of ONE related record
        (patient / team / event / injury) of an activity (task 1595).

        ``url`` is False — and the name the activity's own ``res_name`` /
        nothing — when the viewer may not open that record: the same gate
        as the page the link leads to (``_check_access_to_*``) AND the
        record rules (``has_access('read')``), so a row never links to a
        403 nor reads a field the viewer may not see. Returns None for a
        model the portal has no page for or a deleted record."""
        model = record._name
        if model not in self._SC_ACTIVITY_RELATED_KINDS or not record.exists():
            return None
        pattern, icon = self._SC_ACTIVITY_RELATED_KINDS[model]
        checks = {
            'sports.patient': self._check_access_to_patient,
            'sports.team': self._check_team_access,
            'sports.event': self._check_access_to_event,
            'sports.patient.injury': self._check_access_to_injury,
        }
        try:
            checks[model](record.id)
            allowed = record.has_access('read')
        except (AccessError, MissingError, UserError):
            allowed = False
        link = {'model': model, 'id': record.id, 'icon': icon, 'url': False, 'name': ''}
        if not allowed:
            return link
        link['url'] = pattern % record.id
        if model == 'sports.patient.injury' and self._sc_app_shell_active():
            # Task 1616: the injury's open card (no injury page any more).
            link['url'] = self._sc_injury_card_url(record)
        if model == 'sports.patient':
            link['name'] = record._portal_list_name(with_jersey=False)
        elif model == 'sports.patient.injury':
            link['name'] = record.diagnosis or record.display_name
        else:
            link['name'] = record.display_name
        return link

    def _sc_activity_related(self, activity):
        """The links of ``activity``'s related records for its row and
        detail (task 1595): the record it is scheduled on (player / team /
        event, or a legacy injury), then the injury it is ABOUT (task 1409's
        technical ``injury_id``) when there is one. Each entry follows
        ``_sc_activity_record_link``; a record the viewer may not open comes
        with ``url`` False and the activity's ``res_name`` as its label
        (already visible to whoever sees the activity), never a link.
        sudo(): only to read the activity's own target ids — every label
        and link is gated per record above."""
        act = activity.sudo()
        links = []
        if act.res_model and act.res_id and act.res_model in self._SC_ACTIVITY_RELATED_KINDS:
            link = self._sc_activity_record_link(request.env[act.res_model].browse(act.res_id))
            if link:
                if not link['url']:
                    link['name'] = act.res_name or ''
                if link['name']:
                    links.append(link)
        if act.injury_id and not (act.res_model == 'sports.patient.injury'
                                  and act.res_id == act.injury_id.id):
            link = self._sc_activity_record_link(request.env['sports.patient.injury'].browse(act.injury_id.id))
            # An injury the viewer may not open is not named at all (its
            # diagnosis is medical data; the summary prefix already says
            # what the activity is about to those allowed to read it).
            if link and link['url']:
                links.append(link)
        return links

    @staticmethod
    def _sc_title_find(title, name):
        """Case-insensitive position of ``name`` in ``title`` (-1 if absent)."""
        if not name:
            return -1
        lowered = title.lower()
        if len(lowered) != len(title):
            return title.find(name)
        return lowered.find(name.lower())

    def _sc_activity_title_parts(self, title, links):
        """Owner review 2026-10-14: an activity row's title split so the
        related record's name in it is a link to that record — ``[{text[,
        url, model]}]`` segments, the first (earliest, then longest) name of
        an ALLOWED link of ``links`` (``_sc_activity_related``: a record the
        viewer may not open has no url and stays plain text). The names
        looked for: the link's label and the record's own name / display
        name (« One, Pat » or « Pat One »). One plain segment when no name
        shows in the title."""
        title = title or ''
        best = None
        for link in links or ():
            if not link.get('url') or not link.get('model') or not link.get('id'):
                continue
            # sudo: names only, of a record the link gate already allowed.
            record = request.env[link['model']].sudo().browse(link['id'])
            names = {link.get('name') or ''}
            if 'name' in record._fields:
                names.add(record.name or '')
            names.add(record.display_name or '')
            for name in sorted({n.strip() for n in names if n and n.strip()}, key=len, reverse=True):
                pos = self._sc_title_find(title, name)
                if pos < 0:
                    continue
                if best is None or (pos, -len(name)) < (best[0], -best[1]):
                    best = (pos, len(name), link)
                break
        if best is None:
            return [{'text': title}]
        pos, length, link = best
        parts = [{'text': title[:pos]}] if pos else []
        parts.append({'text': title[pos:pos + length], 'url': link['url'], 'model': link['model']})
        if title[pos + length:]:
            parts.append({'text': title[pos + length:]})
        return parts

    # ------------------------------------------------------------------
    # Task 1593 — player rows carry the legacy card's content
    # ------------------------------------------------------------------
    def _sc_team_links(self, teams):
        """``{team_id: link}`` for ``teams`` (sc_row_links dicts: name, url,
        icon, model). ``url`` is False — the name stays plain text — when the
        viewer may not open the team page: ``_check_team_access``'s rule
        (staff, clinic administrator, or the historical portal-TP branch)
        AND the record rules (one search for the whole set), so a link never
        leads to a refusal. sudo() reads the names only."""
        env = request.env
        teams = teams.sudo()
        if not teams:
            return {}
        readable = set(env['sports.team'].search([('id', 'in', teams.ids)]).ids)
        user = env.user
        if not (self._is_clinic_admin()
                or user.has_group('bemade_sports_clinic.group_portal_treatment_professional')):
            readable &= set(user.partner_id.team_staff_rel_ids.mapped('team_id').ids)
        return {team.id: {
            'name': team.name or '',
            'url': '/my/team?team_id=%s' % team.id if team.id in readable else False,
            'icon': 'teams',
            'model': 'sports.team',
        } for team in teams}

    def _sc_player_row_extras(self, players, team_links=True, team=None):
        """The legacy card's content for each row of ``players`` (task 1593),
        ``{player_id: {...}}`` — computed for the whole list at once (the
        teams, their names and the readable set in a few queries, never per
        row):

        * ``training``: the training recommendation on one line (the row
          truncates it; the expanded detail shows it whole);
        * ``injured`` / ``return_label``: « Retour prévu » for an injured
          player — the date, or « — » when unset (the legacy hint);
        * ``team_links``: the player's teams as links (``_sc_team_links``),
          empty when ``team_links`` is False (a team's own page, as legacy);
        * ``detail_url``: the lazy expanded detail (``row-detail`` route),
          with the team context when given.

        Task 1592: ``clock`` — the activity clock chip (``_sc_activity_clocks``,
        ONE grouped query for the whole list), opening the player page's
        Activities tab (with the team context when given); None at 0."""
        env = request.env
        links = self._sc_team_links(players.sudo().team_ids) if team_links else {}
        team_qs = '&team_id=%s' % team.id if team else ''
        clocks = self._sc_activity_clocks(
            players, lambda p: '/my/player?player_id=%s%s&tab=activities' % (p.id, team_qs))
        extras = {}
        for player in players:
            injured = (player.stage or 'healthy') != 'healthy'
            text = ' '.join((player.training_recommendation or '').split())
            return_label = False
            if injured:
                return_label = (format_date(env, player.predicted_return_date)
                                if player.predicted_return_date else '—')
            detail_url = '/my/player/%s/row-detail' % player.id
            if team:
                detail_url += '?team_id=%s' % team.id
            extras[player.id] = {
                'training': text,
                'injured': injured,
                'return_label': return_label,
                'team_links': [links[t.id] for t in player.sudo().team_ids if t.id in links],
                'detail_url': detail_url,
                'clock': clocks.get(player.id),
            }
        return extras

    # ------------------------------------------------------------------
    # Task 1592 — the activity clock on player / team / event rows and
    # injury cards
    # ------------------------------------------------------------------
    def _sc_activity_clocks(self, records, url):
        """``{record_id: clock}`` for the clock chip (``sc_activity_clock``)
        of every row of a list — the activities ASSIGNED TO THE VIEWER on
        each record (an injury: the patient-scoped activities about it, task
        1409's ``injury_id``) and how many of them are overdue, in ONE
        grouped query for the whole list (never a per-row ``search_count``;
        ``sports.team.activity_count`` is per record).

        ``clock``: ``{'count', 'overdue', 'url', 'label'}``; ``url`` (from
        ``url(record)``) is the record's own activities section. A record
        with none is absent: the chip is hidden at 0.

        sudo(): the domain is restricted to the viewer's OWN assignments on
        records the caller already lists (and may open); mail.activity's
        per-document access check would add a query per model."""
        if not records:
            return {}
        env = request.env
        if records._name == 'sports.patient.injury':
            key = 'injury_id'
            domain = [('injury_id', 'in', records.ids)]
        else:
            key = 'res_id'
            domain = [('res_model', '=', records._name), ('res_id', 'in', records.ids)]
        domain.append(('user_id', '=', env.uid))
        today = fields.Date.context_today(env.user)
        counts = {}
        for target, deadline, count in env['mail.activity'].sudo()._read_group(
                domain, [key, 'date_deadline:day'], ['__count']):
            target_id = target.id if key == 'injury_id' else target
            total, overdue = counts.get(target_id, (0, 0))
            late = count if deadline and fields.Date.to_date(deadline) < today else 0
            counts[target_id] = (total + count, overdue + late)
        clocks = {}
        for record in records:
            total, overdue = counts.get(record.id, (0, 0))
            if not total:
                continue
            label = (env._("My activities: %(count)s (%(overdue)s overdue)",
                           count=total, overdue=overdue)
                     if overdue else env._("My activities: %(count)s", count=total))
            clocks[record.id] = {
                'count': total,
                'overdue': overdue,
                'url': url(record),
                'label': label,
            }
        return clocks

    @classmethod
    def _activity_scope_teams(cls):
        """The teams whose activities the viewer lists / acts on (task 1577
        review, 2026-09-29): EVERY team for a clinic administrator (or
        system admin), the teams they staff first; the teams the viewer
        staffs (their staff rows, unchanged) for everyone else. Never a
        bare ``search([])`` for a non-admin."""
        env = http.request.env
        staffed = env.user.partner_id.team_staff_rel_ids.mapped('team_id')
        if cls._is_clinic_admin():
            return cls._staffed_first(
                env['sports.team'].search([], order='name'), staffed)
        return staffed

    @staticmethod
    def _access_denied_message(kind='team'):
        """The clean, translated refusal of a team / player / injury / event
        (task 1577 review, 2026-09-29). Shown instead of the raw exception
        text — an ORM record-rule AccessError carries Odoo's « top secret »
        message and the user / record ids, never fit for a portal page."""
        if kind == 'patient':
            return _("You do not have access to this patient.")
        if kind == 'injury':
            return _("You do not have access to this injury.")
        if kind == 'event':
            return _("You do not have access to this event.")
        return _("You do not have access to this team.")

    @classmethod
    def _access_denied(cls, exc, kind='team'):
        """Log the real refusal server-side and return the clean message
        (see ``_access_denied_message``)."""
        _logger.info("Portal %s access refused for user %s: %s",
                     kind, http.request.env.uid, exc)
        return cls._access_denied_message(kind)

    @classmethod
    def _user_error_text(cls, exc, kind='team'):
        """The text of ``exc`` fit for a portal page / flash / notification.

        Our own UserError / ValidationError / AccessError messages are
        single-line and meant for the user: kept as is. The ORM's ACL,
        record-rule and missing-record errors are multi-line (« Oups ! …
        top secret … (id=…) … cookies ») and carry user / record ids: those
        are logged and replaced with the clean refusal of ``kind``
        (1577 review, 2026-09-29)."""
        message = str(exc.args[0]) if getattr(exc, 'args', None) else str(exc)
        if isinstance(exc, (AccessError, MissingError)) and '\n' in message:
            return cls._access_denied(exc, kind)
        return message

    def _admin_or_staffed_teams(self, staffed):
        """The team TARGET list of a form (add-to-team, create player, …):
        ``staffed`` (the caller's own staffed-teams set, unchanged) for
        everyone but a clinic administrator, who gets EVERY team with the
        staffed ones first (task 1577)."""
        if not self._is_clinic_admin():
            return staffed
        return self._staffed_first(
            http.request.env['sports.team'].search([], order='name'), staffed)

    def _get_organizations(self):
        """Organizations (parent partners) of the accessible teams.

        sudo(): these are only rendered as filter labels (name/id) for teams
        the user already staffs, and the res.partner record rules deny plain
        portal users (e.g. staff role 'other') the read outright — /my/players
        403'd at render (dev-review 2026-07-04 round 2)."""
        teams = self._get_accessible_teams()
        organizations = teams.sudo().mapped('parent_id').filtered(lambda p: p)
        return organizations.sorted('name')

    def _get_all_teams(self):
        """Every team, for the events-list filter dropdown (task 1226).

        The dropdown lists *all* teams regardless of the user's assignment so a
        coach can scope the list to any team. This widens only the *filter
        options*, not record visibility: selecting a team they don't staff still
        returns no events because the sports.event coach record rule keeps event
        reads team-scoped, and the event/team/org detail routes have their own
        gating (_check_access_to_event / _check_team_access).

        sudo() is required because the sports.team record rules scope portal
        users (coaches and therapists) to the teams they staff / share patients
        with, so a non-sudo search([]) would return only their own teams and
        defeat the purpose. Only names/ids are rendered from this set.
        """
        return http.request.env['sports.team'].sudo().search([], order='name')

    def _get_all_organizations(self):
        """Parent organizations of every team, for the events-list filter
        dropdown (task 1226). See _get_all_teams for the sudo rationale."""
        teams = self._get_all_teams()
        organizations = teams.mapped('parent_id').filtered(lambda p: p)
        return organizations.sorted('name')

    # ------------------------------------------------------------------
    # Post/Redirect/Get helpers for form-validation errors.
    # On a validation failure a submit handler stashes the message (and the
    # submitted fields) in the session and redirects (GET) back to the form;
    # the form's GET handler calls _portal_pop_flash() to render them. This
    # avoids re-POST-on-refresh and the fragile "re-render the form template
    # inline" pattern (which repeatedly 500'd on missing template context).
    # ------------------------------------------------------------------

    # Task 1600: the flash is SCOPED to the form it belongs to and EXPIRES.
    # A flash stashed by player A's failed save used to stay in the session
    # until ANY form popped it — and the player edit form then filled player
    # B's fields (and unticked B's teams) from A's posted data. Now a pop
    # returns the data only for the same scope (e.g. ('player_edit', A.id))
    # and within PORTAL_FLASH_TTL seconds; any other pop discards it.
    PORTAL_FLASH_TTL = 600

    @staticmethod
    def _portal_flash_scope(scope):
        return [str(part) for part in (scope if isinstance(scope, (list, tuple)) else (scope,))]

    def _portal_flash(self, error, form_data=None, scope=None):
        """Stash a validation error + submitted form data for a PRG redirect
        to the form identified by ``scope`` (a tuple such as
        ``('player_edit', patient_id)``)."""
        request.session.pop('portal_flash_error', None)
        request.session.pop('portal_flash_data', None)
        data = request.httprequest.form.to_dict(flat=False) if form_data is None else form_data
        clean = {}
        for key, value in dict(data or {}).items():
            if key == 'csrf_token':
                continue
            if isinstance(value, (list, tuple)):
                value = list(value) if len(value) > 1 else (value[0] if value else '')
            clean[key] = value
        request.session['portal_flash'] = {
            'scope': self._portal_flash_scope(scope),
            'ts': systime.time(),
            'error': error,
            'data': clean,
        }

    def _portal_pop_flash(self, scope=None):
        """Return (error, form_data) stashed by _portal_flash for ``scope``,
        clearing the flash in every case. A flash of another scope, or older
        than PORTAL_FLASH_TTL, is discarded: (None, {})."""
        # Pre-1600 sessions: the unscoped keys are dropped, never used.
        request.session.pop('portal_flash_error', None)
        request.session.pop('portal_flash_data', None)
        flash = request.session.pop('portal_flash', None)
        if not isinstance(flash, dict):
            return None, {}
        if flash.get('scope') != self._portal_flash_scope(scope):
            return None, {}
        try:
            age = systime.time() - float(flash.get('ts') or 0)
        except (TypeError, ValueError):
            return None, {}
        if age < 0 or age > self.PORTAL_FLASH_TTL:
            return None, {}
        return flash.get('error'), dict(flash.get('data') or {})

    def _activity_assignable_users(self):
        """Active users in either treatment-professional group OR the
        portal team-coach group, name order.

        The single source of truth for who can be assigned an activity from
        the portal (task 1402, shared here since task 1408 so the player-
        and team-page Activities tabs use the SAME list): ALL treatment
        professionals and ALL team coaches (task 1426), everywhere — no
        team-staff narrowing, no plain portal users, no internal non-TP
        staff. Access gaps are flagged by the advisory warning at assignment
        time instead of by narrowing this list. This is the TP / admin
        branch of :meth:`_activity_assignable_users_for`, which is the
        per-actor rule every dropdown and POST guard goes through (task
        1500).

        sudo(): the base record rule ``base.res_users_rule_portal`` restricts
        portal users to users of their own commercial partner, which would
        collapse this list to "self" for every portal TP. The owner-approved
        scope is ALL treatment professionals; only ids and names from this
        recordset are ever rendered, and the POST guards only use it for a
        membership check.

        ``all_group_ids`` (not ``group_ids``): in Odoo 19 ``group_ids`` holds
        only the DIRECTLY assigned groups, so an internal user who is a TP by
        implication (clinic Administrator implies the internal TP group) was
        silently missing from the picker while ``has_group`` said yes.
        """
        portal_tp = http.request.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        internal_tp = http.request.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        coach = http.request.env.ref('bemade_sports_clinic.group_portal_team_coach')
        return http.request.env['res.users'].sudo().search(
            [('all_group_ids', 'in', [portal_tp.id, internal_tp.id, coach.id]), ('active', '=', True)],
            order='name')

    def _activity_assignable_users_for(self, user=None):
        """Users ``user`` (default: the current user) may assign an activity
        to — the ONE per-actor rule behind every assignee dropdown AND every
        POST guard of the activity portal (task 1500):

        * a treatment professional (portal or internal) or an admin → the
          full list of :meth:`_activity_assignable_users` (all TPs + all
          coaches), unchanged;
        * a portal team coach → the STAFF OF THE COACH'S OWN TEAMS: every
          active user whose partner holds a ``sports.team.staff`` row (any
          role, any source) on a team where the coach's partner also holds
          one, plus the coach themself — never staff of other teams or
          organizations, never a TP who staffs none of those teams;
        * anyone else → themself only.

        The dropdowns render only ids/names from the result; the guards use
        it for a membership check only, so a forged POST can never widen it.

        sudo(): same rationale as :meth:`_activity_assignable_users` — the
        portal record rules on res.users / sports.team.staff would collapse
        the searches to the actor's own commercial partner or teams.
        """
        env = http.request.env
        user = (user or env.user).sudo()
        if (user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
                or user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
                or user.has_group('base.group_system')):
            return self._activity_assignable_users()
        Users = env['res.users'].sudo()
        if not user.has_group('bemade_sports_clinic.group_portal_team_coach'):
            return Users.browse(user.id)
        Staff = env['sports.team.staff'].sudo()
        own_teams = Staff.search([('partner_id', '=', user.partner_id.id)]).team_id
        partners = Staff.search([('team_id', 'in', own_teams.ids)]).partner_id
        # head_coach_id / head_therapist_id are computed FROM the staff rows
        # (sports.team._compute_head_coach_id / _compute_head_therapist_id),
        # so this union is a no-op today; kept so the rule survives a future
        # de-materialisation of those fields.
        partners |= own_teams.head_coach_id | own_teams.head_therapist_id
        return Users.search([
            '&', ('active', '=', True),
            '|', ('id', '=', user.id), ('partner_id', 'in', partners.ids),
        ], order='name')

    # ------------------------------------------------------------------
    # Clinic navigation context (task 1410).
    # A therapist who opens a player (or any of its sub-pages) FROM a clinic
    # worklist keeps a `clinic_id` query/form parameter along the way, so the
    # breadcrumbs read Home / Clinics / <Clinic> / <Player> / <Page> and the
    # « Clinic » crumb returns to /my/clinic/<id>?patient=<pid>#clinic-dossier.
    # The parameter is NAVIGATION ONLY: it is re-validated on every request
    # (accessible event, really a clinic, clinic user) and silently dropped
    # when invalid, so the page renders exactly as without it. Access to the
    # player / injury is never derived from it.
    # ------------------------------------------------------------------

    def _clinic_context(self, params=None):
        """The clinic named by ``clinic_id`` in ``params`` (or the request),
        as a sports.event recordset — EMPTY when missing, malformed, not a
        clinic, or not accessible to the user. Never raises."""
        raw = None
        if params:
            raw = params.get('clinic_id')
        if not raw:
            raw = request.params.get('clinic_id')
        try:
            clinic_id = int(raw)
        except (TypeError, ValueError):
            return request.env['sports.event']
        user = request.env.user
        is_clinic_user = (
            user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
            or user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
            or user.has_group('base.group_system'))
        if not is_clinic_user:
            return request.env['sports.event']
        try:
            event = self._check_access_to_event(clinic_id)
        except UserError:  # AccessError / MissingError are UserErrors
            return request.env['sports.event']
        if event.sudo().event_type != 'clinic':
            return request.env['sports.event']
        return event

    @staticmethod
    def _with_clinic(url, clinic):
        """``url`` with ``clinic_id=<id>`` appended (before any #fragment)
        when ``clinic`` is set; ``url`` unchanged otherwise."""
        if not clinic or not url:
            return url
        base, _, frag = url.partition('#')
        if 'clinic_id=' in base:
            return url
        sep = '&' if '?' in base else '?'
        return f'{base}{sep}clinic_id={clinic.id}' + (f'#{frag}' if frag else '')

    @staticmethod
    def _clinic_return_url(clinic, patient_id, anchor='clinic-dossier'):
        """The clinic page with ``patient_id`` selected and the dossier in view."""
        url = '/my/clinic/%s' % clinic.id
        if patient_id:
            url += '?patient=%s' % patient_id
        if anchor:
            url += '#' + anchor
        return url

    @staticmethod
    def _url_with_query(url, query):
        """``url`` with ``query`` (``key=value``) appended before any
        #fragment — the generic form of ``_with_clinic`` (task 1411), used to
        add ``success=``/``error=`` to a caller-supplied return URL."""
        if not url or not query:
            return url
        base, _, frag = url.partition('#')
        sep = '&' if '?' in base else '?'
        return f'{base}{sep}{query}' + (f'#{frag}' if frag else '')

    @staticmethod
    def _is_treatment_professional():
        """Portal OR internal treatment professional (task 1411) — exactly the
        groups the TP-only patient fields (team_info_notes, allergies) are
        restricted to, so a template guarded by this never reads a field the
        user may not see."""
        user = request.env.user
        return (
            user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
            or user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))

    @staticmethod
    def _is_clinic_admin():
        """Clinic administrator (``group_sports_clinic_admin``, which implies
        the internal TP group) or system administrator (task 1577). Owner
        decision 2026-09-28: they see and act on ALL teams in the portal/app,
        not only the teams they staff; their record rules are already global."""
        user = request.env.user
        return (
            user.has_group('bemade_sports_clinic.group_sports_clinic_admin')
            or user.has_group('base.group_system'))

    def _is_tp_or_system(self):
        """A treatment professional (portal OR internal) or a system admin —
        the portal-or-internal form of the historical « portal TP or
        base.group_system » gate (task 1577). An instance method on purpose:
        TaskManagementPortal redefines _is_treatment_professional as one, and
        every portal controller is merged into one class at runtime."""
        return self._is_treatment_professional() or request.env.user.has_group('base.group_system')

    @staticmethod
    def _is_clinic_page_url(url):
        """True when ``url`` is a local path to a clinic page (/my/clinic/<id>…)
        — the gate for the clinic-aware redirects of the injury create / save
        handlers (task 1412). Pass the value through ``_local_return_url``
        first; this only looks at the prefix."""
        return bool(url) and isinstance(url, str) and url.startswith('/my/clinic/')

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

    @staticmethod
    def _int_or_none(value):
        """``int(value)`` or None for a missing / malformed query value
        (task 1413: the ``note_id`` an edit bounce carries)."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_return_url(value, fallback, prefixes=None):
        """``value`` if it is a same-site relative path, else ``fallback``
        (task 1544: no open redirect through a posted ``return_url``).

        Task 1579: ONE validator for the whole addon —
        ``models/sc_app_nav.safe_return_url`` (same rule as before, plus the
        optional ``prefixes`` the events pages restrict themselves to)."""
        return sc_app_nav.safe_return_url(value, fallback, prefixes=prefixes)

    @classmethod
    def _local_return_url(cls, value, default):
        """``value`` if it is a local absolute path (the addon's return_url
        convention), else ``default`` — never redirect off-host. Same rule as
        ``_safe_return_url`` (kept for existing callers)."""
        return cls._safe_return_url(value, default)

    def _check_team_access(self, team_id, check_staff=False):
        """
        Verify the current user has access to this team.
        
        :param int team_id: ID of the team to check access for
        :param bool check_staff: If True, only allow team staff members
        :return: The team record if access is granted
        :raises: MissingError if team not found
        :raises: AccessError if user doesn't have permission
        """
        team = request.env['sports.team'].browse(int(team_id))
        if not team.exists():
            raise MissingError(_("Team not found"))
            
        user = request.env.user
        
        # Check if user is a staff member of this team. A team the record
        # rules refuse raises the ORM's raw « top secret » AccessError on
        # this read: log it, raise the clean refusal instead (1577 review).
        try:
            is_team_staff = team.staff_ids.filtered(
                lambda s: user.partner_id in s.user_ids.partner_id
            )
        except AccessError as exc:
            raise AccessError(self._access_denied(exc, 'team')) from None
        
        if check_staff and not is_team_staff:
            # Only team staff can perform certain actions
            raise AccessError(_("Only team staff members can perform this action."))

        # Task 1577 (owner decision 2026-09-28): a clinic administrator opens
        # ANY team. Checked after check_staff so staff-only actions stay
        # staff-only.
        if is_team_staff or self._is_clinic_admin():
            return team

        # Historical portal-TP branch, kept as is. An internal (non-admin) TP
        # does NOT get it: they need a staff row, exactly like a portal TP
        # whose team record rule refuses a non-staffed team anyway.
        is_treatment_professional = request.env.user.has_group(
            'bemade_sports_clinic.group_portal_treatment_professional'
        )
        if not is_treatment_professional:
            raise AccessError(self._access_denied_message('team'))
            
        return team
    
    # NOTE: _check_team_staff_access and _check_treatment_professional_access
    # were removed in task 1260. They existed ONLY to gate the portal
    # remove-player route, and their union was LOOSER than the model's removal
    # policy (any staff role could remove; the portal TP check ignored which
    # team). That route now calls the model's remove_from_team, whose single
    # _may_remove_from_team predicate is the one source of truth. Do not
    # reintroduce a portal-local removal check — it will drift from the model.

    def _check_access_to_patient(self, patient_id):
        """
        Verify the user has access to this patient.
        
        :param int patient_id: ID of the patient to check access for
        :return: The patient record if access is granted
        :raises: UserError if user doesn't have permission or patient not found
        """
        user = request.env.user
        patient = request.env['sports.patient'].browse(int(patient_id))
        
        if not patient.exists():
            raise MissingError(_('Patient not found.'))

        # Record access is team-gated for EVERYONE, including treatment
        # professionals: a TP may find an unteamed patient in portal search
        # (task 640) to add them to a team, but full patient-record access
        # requires being staff on one of the patient's teams. System admins
        # always pass; so do clinic administrators (task 1577: they act on
        # every team, and their record rules are global).
        if self._is_clinic_admin():
            return patient

        # Check if user has access through team staff relationships (original task portal logic)
        user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
        try:
            patient_teams = patient.team_ids
        except AccessError as exc:
            raise AccessError(self._access_denied(exc, 'patient')) from None

        # User must be staff on at least one of the patient's teams
        has_team_access = bool(user_teams & patient_teams)

        # Treatment professionals still need to be staff on the patient's teams
        # They don't get blanket access to all patients
        if not has_team_access:
            raise AccessError(_('You do not have access to this patient.'))

        return patient
    
    def _check_access_to_injury(self, injury_id):
        """
        Verify the user has access to this injury.
        
        :param int injury_id: ID of the injury to check access for
        :return: The injury record if access is granted
        :raises: UserError if user doesn't have permission or injury not found
        """
        user = request.env.user
        injury = request.env['sports.patient.injury'].browse(int(injury_id))
        
        if not injury.exists():
            raise MissingError(_('Injury not found.'))

        # Team-gated for everyone (see _check_access_to_patient, task 640).
        # System admins and clinic administrators always pass (task 1577).
        if self._is_clinic_admin():
            return injury

        # Check if user has access through team staff relationships (original task portal logic)
        user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
        try:
            patient_teams = injury.patient_id.team_ids
        except AccessError as exc:
            raise AccessError(self._access_denied(exc, 'injury')) from None

        # User must be staff on at least one of the patient's teams
        has_team_access = bool(user_teams & patient_teams)

        # Treatment professionals still need to be staff on the patient's teams
        # They don't get blanket access to all injuries
        if not has_team_access:
            raise AccessError(_('You do not have access to this injury.'))

        return injury

    def _check_access_to_event(self, event_id):
        """Verify the user has access to this event.

        Mirror the access semantics used by the event portal:
        - treatment professionals can access event records
        - coaches must be staff on at least one of the event teams
        - system users always allowed
        """
        user = request.env.user
        event = request.env['sports.event'].browse(int(event_id))

        if not event.exists():
            raise MissingError(_('Event not found.'))

        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
            user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')

        if user.has_group('base.group_system'):
            return event

        if is_therapist:
            return event

        if is_coach:
            user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
            try:
                has_team_access = bool(user_teams & event.team_ids)
            except AccessError as exc:
                raise AccessError(self._access_denied(exc, 'event')) from None
            if not has_team_access:
                raise AccessError(_('You do not have access to this event.'))
            return event

        raise AccessError(_('You do not have access to this event.'))
    
    def _check_access_to_task_model(self, model_name, record_id):
        """
        Verify the user has access to a task-related model record.
        
        :param str model_name: Name of the model ('sports.patient', 'sports.team', 'sports.event').
            Task 1409: 'sports.patient.injury' is no longer an activity target.
        :param int record_id: ID of the record to check access for
        :return: The record if access is granted
        :raises: UserError if user doesn't have permission or record not found
        """
        valid_models = ['sports.patient', 'sports.team', 'sports.event']
        if model_name not in valid_models:
            raise UserError(_('Invalid model specified.'))
        
        if model_name == 'sports.patient':
            return self._check_access_to_patient(record_id)
        elif model_name == 'sports.team':
            return self._check_team_access(record_id)
        elif model_name == 'sports.event':
            return self._check_access_to_event(record_id)
        
        # This should never be reached due to the valid_models check above
        raise UserError(_('Invalid model specified.'))
