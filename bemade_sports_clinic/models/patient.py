from odoo import models, fields, _, api, Command, SUPERUSER_ID
from odoo.exceptions import ValidationError, AccessError, UserError
from datetime import date, datetime, timedelta
import re
import unicodedata
from dateutil.relativedelta import relativedelta
from odoo.addons.phone_validation.tools import phone_validation
from .patient_injury import (
    dashboard_external_injury_fields,
    dashboard_internal_injury_fields,
    legacy_change_emails_enabled,
)
import logging

_logger = logging.getLogger(__name__)

# Roles that may DIRECTLY remove a player from a team (both the internal
# recordset path and the portal route). Everyone else must use the Request
# Removal flow, which routes a task to the head therapist. head_therapist is
# mandatory: the removal-request workflow assigns its activity to the head
# therapist, so a head therapist must be able to action it (task 1260).
REMOVAL_ROLES = ('therapist', 'head_therapist')

external_tracking_fields = {
    "last_consultation_date",
    "match_status",
    "practice_status",
    "predicted_return_date",
    # Task 1381: return_date untracked from the dashboard changelog — injury
    # resolution already surfaces via match_status/practice_status (both still
    # tracked), so a return_date line is redundant. Still tracking=True on the
    # field (chatter keeps it). The synopsis phrase "Return date updated" below
    # is now dead-but-harmless. Forward-only.
    # Task 1272 (deferred from #1339): a training-recommendation edit is
    # coach-visible clinical guidance, so it bumps BOTH roles and surfaces as a
    # digest change-item. This is the ONE tracked-field addition for #1272 (the
    # broader "what counts as a change" review is #1343). NB: the plan text said
    # "patient_injury.py"; training_recommendation is a sports.patient field, so
    # the correct home is this patient-level external set — the one
    # _propagate_patient_dashboard checks.
    "training_recommendation",
}

# Task 1381: date_of_birth untracked from the dashboard changelog (still
# tracking=True on the field, so chatter still records it). Forward-only.
internal_tracking_fields = {
    "team_info_notes",
    "age",
}

# --- Team-dashboard rollup (task 1272) --------------------------------------
# Ranking weight per clinical stage; more concerning stages score higher so the
# most urgent players surface first on the dashboards.
DASHBOARD_STAGE_WEIGHT = {"no_play": 3, "practice_ok": 2, "healthy": 1}
# Default recency window (hours) for "recently active" players; overridable via
# the ir.config_parameter below (none is shipped, so the default applies).
DASHBOARD_WINDOW_HOURS_DEFAULT = 24
DASHBOARD_WINDOW_PARAM = "bemade_sports_clinic.dashboard_activity_window_hours"

# --- Team-dashboard change DIGEST (task 1272, re-plan) -----------------------
# The digest flips the dashboard from counting to RENDERING content: for each
# active player it lists ONLY the fields that changed in the window, with their
# CURRENT value, de-duplicated per field. Free text longer than this many
# characters is truncated behind a « voir plus » drill-down.
DASHBOARD_DIGEST_TRUNCATE_LEN = 180
# Category -> Font Awesome icon (shared by the portal cards and the backend
# kanban HTML digest so both surfaces read the same).
DASHBOARD_DIGEST_ICONS = {
    "status": "fa-user",
    "injury": "fa-medkit",
    "new_injury": "fa-plus-circle",
    "note": "fa-sticky-note",
}
# Max synopsis phrases shown on the COLLAPSED card before the remainder folds
# into a "+N more" tail. Keeps the collapsed line to ≤2-3 lines even for the
# busiest player (task 1272, condense round 2). Presentation-only.
DASHBOARD_SYNOPSIS_MAX_PHRASES = 4


class Patient(models.Model):
    _name = "sports.patient"
    _description = "Patient"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    
    _unique_patient = models.Constraint(
        'UNIQUE(partner_id)',
        "A patient with this contact already exists.",
    )
    pending_removal = fields.Boolean(string='Pending Removal', default=False, tracking=True, 
                                    help='Indicates if this player has a pending removal request')
    _order = "sort_order, last_name, first_name"
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help="If unchecked, it means this patient has been archived and won't appear in searches by default.")

    # res.partner fields
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contact",
        ondelete="restrict",
        compute_sudo=True,
    )
    first_name = fields.Char(required=True, tracking=True)
    last_name = fields.Char(required=True, tracking=True)
    name = fields.Char(
        related="partner_id.name",
    )
    phone = fields.Char(related="partner_id.phone", readonly=False)
    street = fields.Char(related="partner_id.street", readonly=False)
    street2 = fields.Char(related="partner_id.street2", readonly=False)
    city = fields.Char(related="partner_id.city", readonly=False)
    state_id = fields.Many2one(related="partner_id.state_id", readonly=False)
    zip = fields.Char(related="partner_id.zip", readonly=False)
    country_id = fields.Many2one(related="partner_id.country_id", readonly=False)
    email = fields.Char(related="partner_id.email", readonly=False)

    # Migration tracking field
    odoo16_patient_id = fields.Integer(
        string='Odoo 16 Patient ID',
        help='Original patient ID from Odoo 16 database for migration tracking',
        index=True
    )

    # Patient fields
    date_of_birth = fields.Date(
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional,bemade_sports_clinic.group_portal_treatment_professional",
        tracking=True,
    )
    age = fields.Integer(
        compute="_compute_age",
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional,bemade_sports_clinic.group_portal_treatment_professional",
    )
    contact_ids = fields.One2many(
        comodel_name="sports.patient.contact",
        inverse_name="patient_id",
        string="Patient Contacts",
        groups="bemade_sports_clinic.group_sports_clinic_user,bemade_sports_clinic.group_portal_treatment_professional",
    )
    team_ids = fields.Many2many(
        comodel_name="sports.team",
        relation="sports_team_patient_rel",
        column1="patient_id",
        column2="team_id",
        string="Teams",
    )
    position = fields.Char(string="Position")
    match_status = fields.Selection(
        # Selection rather than bool for easy expansion later
        selection=[
            ("yes", "Yes"),
            ("no", "No"),
        ],
        required=True,
        default="yes",
        tracking=True,
    )
    practice_status = fields.Selection(
        selection=[("yes", "Yes"), ("no_contact", "Yes, no contact"), ("no", "No")],
        tracking=True,
        required=True,
        default="yes",
    )
    # Therapist's free-text guidance on what the player can do in training.
    # Elaborates practice_status. Authored by treatment professionals; coaches
    # read it (no field-level groups= so it stays coach-readable). Coach-read /
    # TP-write is enforced at the portal (template t-if + controller gate), the
    # same way date_of_birth is handled.
    training_recommendation = fields.Text(string="Training Recommendation", tracking=True)
    injury_ids = fields.One2many(
        comodel_name="sports.patient.injury",
        inverse_name="patient_id",
        string="Injuries",
    )
    treatment_note_ids = fields.One2many(
        comodel_name="sports.treatment.note",
        inverse_name="patient_id",
        string="Treatment Notes",
    )
    treatment_note_count = fields.Integer(
        compute="_compute_treatment_note_count",
        string="Treatment Note Count",
    )
    injured_since = fields.Date(compute="_compute_is_injured")
    predicted_return_date = fields.Date(tracking=True)
    return_date = fields.Date(
        tracking=True,
        help="When the player was cleared by medical staff to " "return to match play.",
    )
    is_injured = fields.Boolean(compute="_compute_is_injured")
    stage = fields.Selection(
        selection=[
            ("no_play", "Injured"),
            ("practice_ok", "Practice OK"),
            ("healthy", "Play OK"),
        ],
        compute="_compute_stage",
    )
    sort_order = fields.Integer(
        string="Roster Sort Order",
        compute="_compute_sort_order",
        store=True,
        help="Status-severity key for roster ordering: 0 = no_play (red), "
        "1 = practice_ok (yellow), 2 = healthy (green). Lower surfaces first.",
    )
    last_consultation_date = fields.Date(tracking=True)
    active_injury_count = fields.Integer(compute="_compute_active_injury_count")
    activity_count = fields.Integer(compute="_compute_activity_count")
    # Documents linked to this patient (optionally to an injury)
    document_ids = fields.One2many(
        comodel_name="sports.injury.document",
        inverse_name="patient_id",
        string="Documents",
    )
    document_count = fields.Integer(
        compute="_compute_document_count",
        string="Document Count",
    )
    allergies = fields.Text(
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional,bemade_sports_clinic.group_portal_treatment_professional",
    )
    team_info_notes = fields.Text(
        string="Notes",
        tracking=True,
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional,bemade_sports_clinic.group_portal_treatment_professional",
    )
    is_anonymized = fields.Boolean(
        string="Anonymized (Law 25)",
        default=False,
        copy=False,
        readonly=True,
        help="Set once this player's personal data has been irreversibly "
        "anonymized under the Law 25 retention policy. Excludes the record "
        "from further anonymization scans.",
    )
    date_left_last_team = fields.Date(
        string="Left Last Team On",
        copy=False,
        help="Date the player was removed from their last team (became "
        "teamless). The Law 25 retention clock for inactive-player "
        "anonymization runs from this date; it is cleared when the player "
        "(re)joins a team. Maintained automatically — not shown on forms.",
    )

    # ----------------------------------------------------------------------
    # Team-dashboard rollup fields (task 1272)
    # ----------------------------------------------------------------------
    # Role-scoped rollups powering the team dashboard (backend page + portal
    # tab) and, later, the #1154 digest slices (C/D). They are NOT computed:
    # they are maintained ON CHANGE by the propagation hooks on this model, its
    # injuries and note history (no cron). Law 25 discipline: internal-only
    # activity (internal_notes; hidden_from_coaches injuries) bumps ONLY the
    # *_tp fields — a coach must never see it, not even as a count. The domain
    # filters on the *_last_activity_* stamp (recency); sort/display use the
    # *_score_* + count fields.
    dashboard_last_activity_coach = fields.Datetime(
        string="Last Coach-visible Activity", index=True, copy=False, readonly=True
    )
    dashboard_last_activity_tp = fields.Datetime(
        string="Last TP-visible Activity", index=True, copy=False, readonly=True
    )
    dashboard_score_coach = fields.Integer(
        string="Coach Dashboard Score", default=0, copy=False, readonly=True
    )
    dashboard_score_tp = fields.Integer(
        string="TP Dashboard Score", default=0, copy=False, readonly=True
    )
    dashboard_new_injury_count_coach = fields.Integer(
        string="Recent New Injuries (Coach)", default=0, copy=False, readonly=True
    )
    dashboard_new_injury_count_tp = fields.Integer(
        string="Recent New Injuries (TP)", default=0, copy=False, readonly=True
    )
    dashboard_note_update_count_coach = fields.Integer(
        string="Recent Note Updates (Coach)", default=0, copy=False, readonly=True
    )
    dashboard_note_update_count_tp = fields.Integer(
        string="Recent Note Updates (TP)", default=0, copy=False, readonly=True
    )
    # Task 1272 (re-plan): rendered change DIGEST for the BACKEND single-column
    # kanban. Non-stored, TP-scoped (the backend team Dashboard tab is internal
    # clinic staff = TP audience). Built from the same role-scoped change-item
    # builder the portal uses, rendered through a shared QWeb fragment. The
    # portal builds its items directly in the controller/template, so it does
    # NOT read this field. sanitize=False so the « voir plus » <details> markup
    # survives (the value is server-generated from a trusted QWeb template).
    dashboard_digest_html = fields.Html(
        string="Change Digest",
        compute="_compute_dashboard_digest_html",
        sanitize=False,
        compute_sudo=True,
    )

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if (
            "team_ids" in fields_list
            and "params" in self.env.context
            and self.env.context.get("params", {}).get("model") == "sports.team"
        ):
            team = self.env["sports.team"].browse(self.env.context.get("params")["id"])
            team_ids = [Command.set([team.id])]
            if team_ids:
                res.update({"team_ids": team_ids})
        return res

    def write(self, vals):
        res = super().write(vals)
        if "team_ids" in vals:
            self.sudo().recompute_followers()
            # sudo(), like recompute_followers above: removing a player from
            # their last team makes them teamless, and the per-record ir.rule
            # that granted the acting therapist/portal user access to them was
            # keyed on that team (cf. task 640). The actor loses read access to
            # the very record whose retention clock we still have to settle. This
            # is a system invariant, not a user edit — it must not depend on who
            # happened to trigger the roster change.
            self.sudo()._sync_date_left_last_team()
        if "first_name" in vals or "last_name" in vals:
            self._recompute_name()
        # Team-dashboard propagation (task 1272). Skip our own rollup writes
        # (dashboard_bump) to avoid recursion.
        if not self.env.context.get("dashboard_bump"):
            self._propagate_patient_dashboard(vals)
        return res

    # ----------------------------------------------------------------------
    # Team-dashboard rollup maintenance (task 1272)
    # ----------------------------------------------------------------------
    @api.model
    def _dashboard_window_hours(self):
        """Recency window (hours) for the team dashboards. Configurable via the
        ``DASHBOARD_WINDOW_PARAM`` ir.config_parameter; defaults to 24h."""
        raw = self.env["ir.config_parameter"].sudo().get_param(
            DASHBOARD_WINDOW_PARAM, DASHBOARD_WINDOW_HOURS_DEFAULT
        )
        try:
            hours = int(raw)
        except (TypeError, ValueError):
            hours = DASHBOARD_WINDOW_HOURS_DEFAULT
        return hours if hours > 0 else DASHBOARD_WINDOW_HOURS_DEFAULT

    @api.model
    def _dashboard_window_cutoff(self):
        return fields.Datetime.now() - timedelta(hours=self._dashboard_window_hours())

    def _dashboard_role_rollup(self, role, cutoff):
        """Return ``(score, new_injury_count, note_update_count)`` for ``role``
        over the recency window, computed from real data.

        Law 25 discipline: the ``coach`` view excludes injuries hidden from
        coaches and internal-scope note history entirely — a coach never sees
        internal clinical activity, not even as a count.
        """
        self.ensure_one()
        injuries = self.injury_ids
        if role == "coach":
            injuries = injuries.filtered(lambda i: not i.hidden_from_coaches)
        new_injuries = injuries.filtered(
            lambda i: i.create_date and i.create_date >= cutoff
        )
        note_domain = [
            ("patient_id", "=", self.id),
            ("note_datetime", ">=", cutoff),
        ]
        if role == "coach":
            note_domain += [
                ("scope", "=", "external"),
                ("injury_id.hidden_from_coaches", "=", False),
            ]
        note_count = (
            self.env["sports.injury.note.history"].sudo().search_count(note_domain)
        )
        stage_weight = DASHBOARD_STAGE_WEIGHT.get(self.stage, 0)
        score = stage_weight * 1000 + len(new_injuries) * 100 + note_count * 10
        return score, len(new_injuries), note_count

    def _bump_dashboard_activity(self, roles):
        """Stamp the given role(s) with ``now`` and refresh their score/counts.

        ``roles`` is a subset of ``('coach', 'tp')``; the CALLER decides which
        roles a change is visible to (Law 25 discipline). Runs sudo: propagation
        can be triggered by a portal coach editing an injury, who has no write
        access to these system-maintained fields on ``sports.patient``.
        """
        roles = tuple(r for r in ("coach", "tp") if r in roles)
        if not roles or not self:
            return
        now = fields.Datetime.now()
        cutoff = self._dashboard_window_cutoff()
        for patient in self:
            vals = {}
            for role in roles:
                score, new_inj, note_cnt = patient._dashboard_role_rollup(role, cutoff)
                vals["dashboard_last_activity_%s" % role] = now
                vals["dashboard_score_%s" % role] = score
                vals["dashboard_new_injury_count_%s" % role] = new_inj
                vals["dashboard_note_update_count_%s" % role] = note_cnt
            patient.sudo().with_context(
                dashboard_bump=True,
                tracking_disable=True,
                mail_notrack=True,
                skip_recompute_followers=True,
            ).write(vals)
        # Task 1401: the SAME stamp, same roles, pushed to the players' teams
        # (write-if-newer) so the portal /my/teams "recent activity" order
        # follows player activity. This is the single stamping site — every
        # dashboard bump (patient fields, injuries, note history) lands here.
        self.sudo().team_ids._bump_last_player_activity(roles, now)

    def _propagate_patient_dashboard(self, values):
        """Bump dashboard rollups for player-level field changes. External
        status (match/practice/return dates) is coach-visible -> both roles;
        internal notes (team_info_notes) are TP-only."""
        changed = set(values)
        if external_tracking_fields & changed:
            self._bump_dashboard_activity({"coach", "tp"})
        elif internal_tracking_fields & changed:
            self._bump_dashboard_activity({"tp"})

    # ----------------------------------------------------------------------
    # Urgent aggregated notifications (task 1269) — 5-min PHI-free cron
    # ----------------------------------------------------------------------
    # A 5-minute cron scans three urgent triggers since a watermark and sends
    # ONE consolidated, PHI-free email per recipient (team coaches + TPs),
    # replacing the per-change follower emails. Law 25: the mail carries only
    # per-team counts, team names, short-notice event name/time and dashboard
    # backlinks — never a player name or any clinical/injury detail.

    _URGENT_WATERMARK_PARAM = "bemade_sports_clinic.urgent_notify_last_run"
    _URGENT_SHORT_NOTICE_HOURS = 24
    _URGENT_STATUS_FIELDS = ("match_status", "practice_status")
    # Task 1427 debounce: hold the summary while urgent activity is still
    # fresh (< QUIET minutes old) so an editing session yields ONE mail, but
    # never hold longer than MAX_DELAY from the oldest pending change.
    _URGENT_QUIET_MINUTES = 10
    _URGENT_MAX_DELAY_MINUTES = 30

    @api.model
    def _urgent_notify_get_watermark(self, now):
        """Datetime lower bound for the scan window. Missing/invalid param ->
        one cron interval back so a fresh install never blasts full history."""
        raw = self.env["ir.config_parameter"].sudo().get_param(
            self._URGENT_WATERMARK_PARAM
        )
        if raw:
            try:
                return fields.Datetime.to_datetime(raw)
            except (ValueError, TypeError):  # pragma: no cover - defensive
                pass
        return now - timedelta(minutes=5)

    @api.model
    def _urgent_notify_set_watermark(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            self._URGENT_WATERMARK_PARAM, fields.Datetime.to_string(value)
        )

    @api.model
    def _urgent_activity_bounds(self, watermark, now):
        """``(earliest, latest)`` datetimes of urgent-relevant activity in
        ``[watermark, now)`` — the same three sources the scans read — or
        ``(None, None)`` when the window is empty. Drives the debounce in
        ``_cron_send_urgent_notifications`` (task 1427)."""
        dates = []
        Message = self.env["mail.message"].sudo()
        status_domain = [
            ("model", "=", "sports.patient"),
            ("date", ">=", watermark), ("date", "<", now),
            ("tracking_value_ids.field_id.name", "in", list(self._URGENT_STATUS_FIELDS)),
        ]
        for order in ("date asc", "date desc"):
            msg = Message.search(status_domain, order=order, limit=1)
            if msg:
                dates.append(msg.date)
        Injury = self.env["sports.patient.injury"].sudo()
        injury_domain = [("create_date", ">=", watermark), ("create_date", "<", now)]
        for order in ("create_date asc", "create_date desc"):
            inj = Injury.search(injury_domain, order=order, limit=1)
            if inj:
                dates.append(inj.create_date)
        for items in self._urgent_scan_short_notice_events(watermark, now).values():
            dates.extend(ev.create_date for ev, _authors in items if ev.create_date)
        if not dates:
            return None, None
        return min(dates), max(dates)

    @api.model
    def _urgent_scan_status_changes(self, watermark, now):
        """{team_id: {patient_id: set(author_partner_id)}} for players whose
        match/practice status changed in ``[watermark, now)`` (read from the
        mail tracking audit).

        The author set threads the originating partner(s) through to
        ``_urgent_notify_build_recipients`` so a recipient is not alerted about
        their own edit (task 1395). A patient can accumulate several tracking
        messages in one window, hence a SET per patient: an item is only dropped
        for a recipient who is its SOLE author. A message with no ``author_id``
        (cron/system write, import) contributes nothing, leaving the set empty —
        which the keep-rule reads as "always notify"."""
        messages = self.env["mail.message"].sudo().search([
            ("model", "=", "sports.patient"),
            ("date", ">=", watermark),
            ("date", "<", now),
        ])
        status_fields = set(self._URGENT_STATUS_FIELDS)
        result = {}
        for msg in messages:
            changed = set(msg.tracking_value_ids.field_id.mapped("name"))
            if not (status_fields & changed):
                continue
            patient = self.browse(msg.res_id).exists()
            if not patient:
                continue
            author = msg.author_id
            for team in patient.team_ids:
                authors = result.setdefault(team.id, {}).setdefault(
                    patient.id, set()
                )
                if author:
                    authors.add(author.id)
        return result

    @api.model
    def _urgent_scan_new_injuries(self, watermark, now):
        """{team_id: {'all': {injury_id: set(author_partner_id)},
        'coach_visible': {injury_id: set(author_partner_id)}}} for injuries
        created in the window. Coach-visible excludes injuries hidden from
        coaches (Law 25 — a coach never sees them, even as a count).

        Each bucket maps the item to its author partner(s) so the per-recipient
        self-authored filter (task 1395) applies TOGETHER with the role scoping,
        never before it. A creator with no ``res.users``/partner leaves the set
        empty — read as "always notify"."""
        injuries = self.env["sports.patient.injury"].sudo().search([
            ("create_date", ">=", watermark),
            ("create_date", "<", now),
        ])
        result = {}
        for inj in injuries:
            teams = inj.patient_id.team_ids
            author = inj.create_uid.partner_id
            authors = {author.id} if author else set()
            for team in teams:
                bucket = result.setdefault(
                    team.id, {"all": {}, "coach_visible": {}}
                )
                bucket["all"].setdefault(inj.id, set()).update(authors)
                if not inj.hidden_from_coaches:
                    bucket["coach_visible"].setdefault(inj.id, set()).update(
                        authors
                    )
        return result

    @api.model
    def _urgent_scan_short_notice_events(self, watermark, now):
        """{team_id: [(sports.event, set(author_partner_id)), ...]} for events
        CREATED in the window whose start is < 24h from their creation time
        (short notice). Normal (>=24h) new events are NOT urgent — they surface
        in the daily digest instead.

        The author set rides alongside each event so the per-recipient
        self-authored filter (task 1395) can drop it for its sole author; the
        summary dict still carries bare ``sports.event`` records."""
        events = self.env["sports.event"].sudo().search([
            ("create_date", ">=", watermark),
            ("create_date", "<", now),
        ])
        threshold = timedelta(hours=self._URGENT_SHORT_NOTICE_HOURS)
        result = {}
        for ev in events:
            if not ev.date_start or not ev.create_date:
                continue
            # Compare against CREATION time (not later edits): a short-notice
            # event is one booked less than 24h before it starts.
            if ev.date_start >= ev.create_date + threshold:
                continue
            author = ev.create_uid.partner_id
            authors = {author.id} if author else set()
            for team in ev.team_ids:
                result.setdefault(team.id, []).append((ev, authors))
        return result

    @api.model
    def _urgent_notify_keep_item(self, authors, partner_id):
        """Task 1395 keep-rule: should an item authored by ``authors`` (a set of
        partner ids) still be reported to ``partner_id``?

        Kept unless the recipient is the item's SOLE author:
          * empty ``authors`` (cron/system write, import, no ``author_id``) ->
            ALWAYS kept — a missing author must never suppress a notification;
          * another author besides the recipient -> kept, that edit is genuine
            news even if the recipient also touched the same item;
          * the recipient alone -> dropped.
        """
        return not authors or bool(authors - {partner_id})

    @api.model
    def _urgent_notify_build_recipients(
        self, status_by_team, injuries_by_team, events_by_team
    ):
        """Map each eligible recipient partner to their per-team summary list.

        Recipients = team coaches + TPs (doctors count as TP), filtered by
        ``_is_follower_eligible`` (which also drops ``silent_notifications``).
        New-injury counts are role-scoped: coaches see coach-visible injuries
        only; TPs see all. Play-status changes and event schedule info are
        visible to both roles. Returns ``{partner_id: [team_summary, ...]}``.

        Counts are computed PER RECIPIENT: each item carries its author
        partner(s) and is dropped from a recipient's copy when that recipient is
        its sole author (task 1395, see ``_urgent_notify_keep_item``). For
        injuries the author filter applies within the role-scoped bucket, never
        before it, so Law-25 hiding is unaffected. A recipient left with nothing
        on every one of their teams never enters the result, so no mail is sent.

        The dashboard ``url`` is likewise per recipient (task 1396): internal
        staff get the backend action link, everyone else the portal team
        dashboard.
        """
        active_team_ids = (
            set(status_by_team) | set(injuries_by_team) | set(events_by_team)
        )
        if not active_team_ids:
            return {}
        base_url = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url"
        ) or ""
        teams = self.env["sports.team"].sudo().browse(sorted(active_team_ids))
        recipients = {}
        for team in teams:
            status_patients = status_by_team.get(team.id, {})
            inj = injuries_by_team.get(
                team.id, {"all": {}, "coach_visible": {}}
            )
            event_items = events_by_team.get(team.id, [])
            # Task 1396: the dashboard link is per RECIPIENT, not per surface.
            # Both variants are plain strings, so build them once per team and
            # pick per recipient inside the staff loop below.
            portal_url = team._dashboard_url(base_url)
            internal_url = team._dashboard_url(base_url, internal=True)
            for staff in team.staff_ids:
                if not staff._is_follower_eligible():
                    continue
                if staff._has_coach_role():
                    role = "coach"
                elif staff._has_therapist_role() or staff.role == "doctor":
                    role = "tp"
                else:
                    continue
                # Needed by the self-authored filter below, hence resolved
                # BEFORE the counts (task 1395).
                partner = staff.partner_id
                if not partner:
                    continue
                # Task 1396: this mail targets the PARTNER, not a user, so the
                # account type has to be inferred from their logins. Only an
                # ACTIVE non-share user grants backend access; the explicit
                # ``u.active`` filter is redundant with the ambient
                # ``active_test`` on ``partner.user_ids`` but keeps the intent
                # legible (and safe if a caller ever runs with active_test off).
                # Note this is NOT the same question as
                # ``_is_follower_eligible``: eligibility inspects ARCHIVED users
                # to DENY notification, this ignores them to PICK a link.
                internal = bool(
                    partner.user_ids.filtered(lambda u: u.active and not u.share)
                )
                keep = self._urgent_notify_keep_item
                status_count = sum(
                    1 for authors in status_patients.values()
                    if keep(authors, partner.id)
                )
                scoped_injuries = (
                    inj["all"] if role == "tp" else inj["coach_visible"]
                )
                new_injury_count = sum(
                    1 for authors in scoped_injuries.values()
                    if keep(authors, partner.id)
                )
                team_events = [
                    ev for ev, authors in event_items
                    if keep(authors, partner.id)
                ]
                if not (new_injury_count or status_count or team_events):
                    continue
                summary = {
                    "name": team.name,
                    "url": internal_url if internal else portal_url,
                    "status_changes": status_count,
                    "new_injuries": new_injury_count,
                    "events": [
                        {"name": ev.name, "date_start": ev.date_start}
                        for ev in team_events
                    ],
                }
                recipients.setdefault(partner.id, []).append(summary)
        return recipients

    @api.model
    def _urgent_notify_fallback_body(self, team_summaries):
        """PHI-free bilingual HTML body used when the mail template is missing
        or fails to render. Counts + team names + short-notice event name/time +
        dashboard links only — never a player name or clinical detail."""
        from markupsafe import Markup, escape
        parts = [Markup(
            "<p>%s</p>" % escape(_(
                "Urgent activity on your teams / Activité urgente sur vos équipes:"
            ))
        )]
        for team in team_summaries:
            lines = [Markup("<p><strong>%s</strong></p>") % escape(team["name"])]
            items = []
            if team["status_changes"]:
                items.append(escape(_(
                    "%s play-status change(s)", team["status_changes"]
                )))
            if team["new_injuries"]:
                items.append(escape(_(
                    "%s new injury/injuries", team["new_injuries"]
                )))
            for ev in team["events"]:
                when = (
                    fields.Datetime.to_string(ev["date_start"])
                    if ev["date_start"] else ""
                )
                items.append(escape(_(
                    "Short-notice new event: %(name)s %(when)s",
                    name=ev["name"] or "", when=when,
                )))
            if items:
                lines.append(
                    Markup("<ul>%s</ul>") % Markup("").join(
                        Markup("<li>%s</li>") % it for it in items
                    )
                )
            if team["url"]:
                lines.append(
                    Markup('<p><a href="%s">%s</a></p>') % (
                        team["url"], escape(_("Team dashboard / Tableau de bord"))
                    )
                )
            parts.append(Markup("").join(lines))
        parts.append(Markup('<p style="color:#888;font-size:12px;">%s</p>') % escape(
            _("No medical data is included. / Aucune donnée médicale n'est incluse.")
        ))
        return Markup("").join(parts)

    @api.model
    def _urgent_notify_send_one(self, partner, team_summaries, lang, template):
        team_count = len(team_summaries)
        body = None
        if template:
            try:
                tmpl = template.sudo().with_context(
                    lang=lang,
                    urgent_teams=team_summaries,
                    urgent_team_count=team_count,
                )
                body = tmpl._render_field("body_html", partner.ids).get(partner.id)
            except Exception:  # pragma: no cover - render guard
                _logger.exception(
                    "Urgent-summary body render failed for partner %s", partner.id
                )
                body = None
        if not body:
            body = self.with_context(lang=lang)._urgent_notify_fallback_body(
                team_summaries
            )
        subject = self.with_context(lang=lang).env._(
            "FitCrew — urgent updates / mises à jour urgentes (%s)", team_count
        )
        try:
            self.env["mail.thread"].sudo().with_context(lang=lang).message_notify(
                partner_ids=partner.ids,
                subject=subject,
                body=body,
                email_layout_xmlid="mail.mail_notification_light",
            )
        except Exception:  # pragma: no cover - never break the cron txn
            _logger.exception(
                "Urgent-summary send failed for partner %s", partner.id
            )

    @api.model
    def _cron_send_urgent_notifications(self, now=None):
        """5-min cron entrypoint. Scans ``[watermark, now)`` for the three
        urgent triggers, sends one PHI-free summary per recipient, then advances
        the watermark (idempotent: a re-run over an already-scanned window finds
        nothing and sends nothing). Missed runs self-heal — the next run covers
        the gap because the watermark only moves on completion.

        ``now`` defaults to the current time; it is injectable so tests can pin a
        deterministic upper bound (all records in a test transaction share the
        transaction-start ``create_date``)."""
        if now is None:
            now = fields.Datetime.now()
        watermark = self._urgent_notify_get_watermark(now)
        if watermark >= now:
            return True
        # Debounce (task 1427): while changes are still landing, hold the
        # whole window — watermark untouched so the next run re-scans it and
        # folds the newer changes into the SAME summary. The hold is bounded
        # by MAX_DELAY from the oldest pending change so a long session still
        # gets its first summary within a known latency.
        earliest, latest = self._urgent_activity_bounds(watermark, now)
        if earliest is not None:
            quiet = timedelta(minutes=self._URGENT_QUIET_MINUTES)
            max_delay = timedelta(minutes=self._URGENT_MAX_DELAY_MINUTES)
            if now - latest < quiet and now - earliest < max_delay:
                _logger.info(
                    "Urgent summary held: activity %s ago (quiet %s), oldest pending %s ago",
                    now - latest, quiet, now - earliest,
                )
                return True
        status_by_team = self._urgent_scan_status_changes(watermark, now)
        injuries_by_team = self._urgent_scan_new_injuries(watermark, now)
        events_by_team = self._urgent_scan_short_notice_events(watermark, now)

        recipients = self._urgent_notify_build_recipients(
            status_by_team, injuries_by_team, events_by_team
        )
        if recipients:
            template = self.env.ref(
                "bemade_sports_clinic.mail_template_urgent_summary",
                raise_if_not_found=False,
            )
            partners = self.env["res.partner"].sudo().browse(list(recipients))
            default_lang = self.env.lang or "en_US"
            by_lang = self.env["sports.event"]._group_partners_by_lang(
                partners, default_lang
            )
            for lang, lang_partners in by_lang.items():
                for partner in lang_partners:
                    self._urgent_notify_send_one(
                        partner, recipients[partner.id], lang, template
                    )
            # Deliver NOW: the summaries are queued mail.mail records and the
            # stock queue manager may run only hourly (prod: three window
            # summaries burst together an hour later, 2026-08-26). Trigger it.
            mail_cron = self.env.ref(
                "mail.ir_cron_mail_scheduler_action", raise_if_not_found=False
            )
            if mail_cron:
                mail_cron.sudo()._trigger()
        # Advance the watermark on completion (also on empty windows).
        self._urgent_notify_set_watermark(now)
        return True

    # ----------------------------------------------------------------------
    # Team-dashboard change DIGEST (task 1272, re-plan): render CONTENT
    # ----------------------------------------------------------------------
    # The counting rollup above answers "did something change, and how urgent";
    # the digest below answers "WHAT changed" — the fields that actually changed
    # in the window, with their current value, de-duplicated per field. It
    # reuses the SAME tracking sets + note-history hook that drive the counts;
    # nothing about the on-change detection changes. Law 25: the role argument
    # is the visibility gate. These methods run sudo (a portal coach can't read
    # tracking values / note history), so the role filter here MUST be airtight
    # — a coach digest must never contain internal-note or hidden-injury content.

    @api.model
    def _dashboard_changed_field_names(self, res_model, res_ids, cutoff):
        """Set of field names on ``res_model``/``res_ids`` whose value changed
        within the window, read from the mail tracking audit (the same trail the
        chatter shows). Fields must be ``tracking=True`` to appear here — that is
        exactly the dashboard tracked-field set."""
        res_ids = [r for r in (res_ids or []) if r]
        if not res_ids:
            return set()
        messages = self.env["mail.message"].sudo().search([
            ("model", "=", res_model),
            ("res_id", "in", res_ids),
            ("date", ">=", cutoff),
        ])
        return set(messages.tracking_value_ids.field_id.mapped("name"))

    def _dashboard_render_value(self, record, field_name):
        """Human-readable CURRENT value of ``field_name`` on ``record``."""
        field = record._fields[field_name]
        value = record[field_name]
        if value is False or value is None or value == "":
            return ""
        ftype = field.type
        if ftype == "selection":
            try:
                selection = dict(field._description_selection(record.env))
            except Exception:  # pragma: no cover - defensive
                raw = field.selection
                selection = dict(raw) if isinstance(raw, (list, tuple)) else {}
            return str(selection.get(value, value))
        if ftype == "many2one":
            return value.display_name or ""
        if ftype in ("many2many", "one2many"):
            return ", ".join(n for n in value.mapped("display_name") if n)
        if ftype == "date":
            return fields.Date.to_string(value)
        if ftype == "datetime":
            return fields.Datetime.to_string(value)
        return str(value).strip()

    def _selection_key_from_label(self, record, field_name, label):
        """Reverse-map a stored selection LABEL back to its selection KEY
        (task 1385, CR-D1). ``mail.tracking.value`` stores a selection change as
        the label rendered in the WRITER's language at write time
        (``old_value_char``), so a French viewer can be shown an English "No".
        We recover the underlying key by matching the stored label against the
        field's selection in EVERY installed language; the caller then re-renders
        that key in the viewer's language for a consistently localized delta.

        Returns the key, or ``None`` when the label can't be resolved (a renamed
        selection option, or a free-text tracking) so the caller can fall back to
        the stored label as-is.
        """
        field = record._fields[field_name]
        label = (label or "").strip()
        if not label:
            return None
        codes = [code for code, _name in self.env["res.lang"].get_installed()]
        if not codes:
            codes = [record.env.lang or self.env.lang or "en_US"]
        for code in codes:
            rec = record.with_context(lang=code)
            try:
                selection = dict(field._description_selection(rec.env))
            except Exception:  # pragma: no cover - defensive
                continue
            for key, lbl in selection.items():
                if str(lbl).strip() == label:
                    return key
        return None

    def _dashboard_field_old_value(self, record, field_name, cutoff):
        """PREVIOUS display value of ``field_name`` on ``record`` — the value it
        held at the start of the window, read from the mail tracking audit (task
        1385, CR-A #4). Returns ``""`` when no in-window tracking exists (e.g. a
        create-only field) so callers can gracefully fall back to just the new
        value.

        The window can hold several edits to the same field; the OLDEST
        tracking's ``old`` value is the pre-window state and the current record
        value is the ``new`` one, so together they read as the net delta the
        coach cares about (``ancienne → nouvelle``), not each intermediate hop.

        Task 1385 (CR-D1): the value is rendered in the VIEWER's language. For a
        selection field the tracking's stored label is snapshotted in the
        writer's language, so we reverse-map it to the selection key and
        re-render it through the field's selection in the viewer's language —
        keeping old and new consistently localized (no English "No" facing a
        French viewer, and no spurious "No → Non" pure-language "change").
        """
        if not cutoff:
            return ""
        field = record._fields[field_name]
        # Messages oldest-first so the combined tracking recordset keeps
        # chronological order; the first tracking for the field carries the
        # pre-window value.
        messages = self.env["mail.message"].sudo().search(
            [
                ("model", "=", record._name),
                ("res_id", "=", record.id),
                ("date", ">=", cutoff),
            ],
            order="date asc, id asc",
        )
        trackings = messages.tracking_value_ids.filtered(
            lambda t: t.field_id.name == field_name
        )
        if not trackings:
            return ""
        raw_old = trackings[0]._format_display_value(field.type, new=False)[0]
        return self._dashboard_normalize_old_value(record, field_name, raw_old)

    # ---------------------------------------------------------------- 1387
    # THE shared net-no-op rule. Both the per-player change FEED
    # (``_dashboard_build_item``) and the batched PRESENCE pass
    # (``_dashboard_card_presence`` / ``_dashboard_injury_presence``) go through
    # these two helpers, so a marker can never disagree with the content it
    # announces (task 1387). Do NOT reimplement the comparison anywhere else.

    def _dashboard_normalize_old_value(self, record, field_name, raw_old):
        """Normalize a RAW ``mail.tracking.value`` old-display value into the
        VIEWER's language (task 1385 CR-D1, extracted for sharing in 1387).

        ``mail.tracking.value`` snapshots a selection change as the LABEL
        rendered in the WRITER's language, so a French viewer can be facing an
        English "No". We reverse-map the stored label to its selection key and
        re-render it in the viewer's language; anything else is returned
        stripped. Empty/absent trackings normalize to ``""``.
        """
        if raw_old is False or raw_old is None or raw_old == "":
            return ""
        field = record._fields[field_name]
        if field.type == "selection":
            key = self._selection_key_from_label(record, field_name, raw_old)
            if key is not None:
                selection = dict(field._description_selection(record.env))
                if key in selection:
                    return str(selection[key]).strip()
        return str(raw_old).strip()

    def _dashboard_is_net_change(self, record, field_name, old_value):
        """Did ``field_name`` NET-change on ``record`` over the window?

        ``old_value`` must ALREADY be normalized through
        ``_dashboard_normalize_old_value`` (both callers do), so an equal pair is
        a genuine net no-op — a round-trip like No → Yes → No, or a pure
        writer/viewer language difference.

        An EMPTY normalized old value means the field held nothing at the start
        of the window: it is a change only if it holds something now. A field
        that was filled and then cleared again within the window (empty → X →
        empty) has nothing to render on either side, so it is a no-op too.
        """
        current = self._dashboard_render_value(record, field_name)
        if not old_value:
            return bool(current)
        return old_value != current

    def _dashboard_build_item(
        self, record, field_name, category, injury=False, cutoff=None
    ):
        """Build one de-dupable change-item dict from a field's current value.

        When ``cutoff`` is given and the category carries a real before/after
        (``status`` / ``injury`` field edits), the pre-window value is attached
        as ``old_value`` so the render can show ``ancienne → nouvelle`` (task
        1385, CR-A #4). New-injury sub-items pass no cutoff — a freshly created
        field has no "previous" to show.

        Task 1385 (CR-D1): returns ``None`` when, after normalizing the old value
        into the viewer's language, it resolves to the SAME value as the current
        one — a net no-op over the window (a round-trip like No → Yes → No, or a
        pure writer/viewer language difference). Such a field genuinely did not
        change from the coach's point of view, so it must not emit a change item.
        Callers append only truthy results.
        """
        field = record._fields[field_name]
        value = self._dashboard_render_value(record, field_name)
        is_long = bool(value) and len(value) > DASHBOARD_DIGEST_TRUNCATE_LEN
        preview = value
        if is_long:
            preview = value[:DASHBOARD_DIGEST_TRUNCATE_LEN].rstrip() + "…"
        old_value = ""
        if cutoff and category in ("status", "injury"):
            old_value = self._dashboard_field_old_value(record, field_name, cutoff)
            # Both old and new are now rendered in the viewer's language, so an
            # equal pair is a genuine net no-op (round-trip or language-only
            # difference) -> suppress the whole item (CR-D1 (b)). Task 1387: the
            # rule lives in ONE place, shared with the batched presence pass.
            if not self._dashboard_is_net_change(record, field_name, old_value):
                return None
        # Task 1272 (round 3, defect 3): use the TRANSLATED field label so the
        # expanded digest reads French wherever the field has an fr_CA
        # translation (app-wide ir.model.fields translation), instead of the raw
        # source ``field.string`` which is always the English definition. This is
        # the same label the form/list views show — not a digest-local override.
        label = (
            record.fields_get([field_name]).get(field_name, {}).get("string")
            or field.string
            or field_name
        )
        return {
            "category": category,
            "field": field_name,
            "label": label,
            "value": value,
            "old_value": old_value,
            "preview": preview,
            "is_long": is_long,
            "injury": injury,
            "icon": DASHBOARD_DIGEST_ICONS.get(category, "fa-pencil"),
        }

    # Task 1385 (CR-A #5): the former ``_dashboard_build_new_injury_item`` unit
    # builder was removed. A new injury is no longer a change-feed unit — it is
    # flagged ``is_new`` in the static card section (see ``_card_injury_detail``)
    # and its notes flow through the normal note feed.

    def _dashboard_change_items(self, role, cutoff=None):
        """Ordered list of change-item dicts for ``role`` over the window.

        Read-only; never mutates. ``role`` in ``('coach', 'tp')`` is the Law-25
        visibility gate: ``coach`` gets external-scope changes on non-hidden
        injuries only; ``tp`` gets internal + external.
        """
        self.ensure_one()
        if role not in ("coach", "tp"):
            return []
        if cutoff is None:
            cutoff = self._dashboard_window_cutoff()
        patient = self.sudo()
        items = []

        # 1. Player-level status changes (deduped per field, current value).
        player_fields = self._dashboard_player_fields(role)
        changed_player = patient._dashboard_changed_field_names(
            "sports.patient", patient.ids, cutoff
        )
        for fname in changed_player & player_fields:
            if fname in patient._fields:
                item = patient._dashboard_build_item(
                    patient, fname, "status", cutoff=cutoff
                )
                if item:  # None -> net no-op over the window (CR-D1)
                    items.append(item)

        # 2. Injuries. Coach never sees a hidden-from-coaches injury at all.
        injuries = patient.injury_ids
        if role == "coach":
            injuries = injuries.filtered(lambda i: not i.hidden_from_coaches)
        new_injuries = injuries.filtered(
            lambda i: i.create_date and i.create_date >= cutoff
        )
        updated_injuries = injuries - new_injuries

        # 2a. New injuries -> NO change-feed unit (task 1385, CR-A #5). A brand
        #     new injury is already surfaced (and flagged "new") in the card's
        #     static active-injury section, so emitting a "Nouvelle blessure …"
        #     row here just duplicates it. Its note history still flows through
        #     section 3 below.

        # 2b. Updated injuries -> only their changed fields (notes handled in 3).
        injury_fields = self._dashboard_injury_field_set(role)
        for injury in updated_injuries:
            changed = patient._dashboard_changed_field_names(
                "sports.patient.injury", injury.ids, cutoff
            )
            for fname in changed & injury_fields:
                if fname in injury._fields:
                    item = patient._dashboard_build_item(
                        injury, fname, "injury", injury=injury, cutoff=cutoff
                    )
                    if item:  # None -> net no-op over the window (CR-D1)
                        items.append(item)

        # 3. Note updates, from the append-only history, scope-filtered. Deduped
        #    to the CURRENT note value per (injury, scope): a burst of edits
        #    reads as ONE item.
        note_domain = [
            ("patient_id", "=", patient.id),
            ("note_datetime", ">=", cutoff),
        ]
        if role == "coach":
            note_domain += [
                ("scope", "=", "external"),
                ("injury_id.hidden_from_coaches", "=", False),
            ]
        histories = self.env["sports.injury.note.history"].sudo().search(note_domain)
        seen_notes = set()
        for hist in histories:
            injury = hist.injury_id
            if not injury:
                continue
            if role == "coach" and injury.hidden_from_coaches:
                continue
            # Task 1385 (CR-A #5): new injuries no longer emit a bundled unit,
            # so their note history is surfaced here like any other note update.
            key = (injury.id, hist.scope)
            if key in seen_notes:
                continue
            seen_notes.add(key)
            note_field = "external_notes" if hist.scope == "external" else "internal_notes"
            if note_field in injury._fields and injury[note_field]:
                item = patient._dashboard_build_item(
                    injury, note_field, "note", injury=injury
                )
                if item:  # note items never no-op out, but guard uniformly
                    items.append(item)
        return items

    # ----------------------------------------------------------------------
    # Homogenized portal card (task 1385): batched presence + lazy-load feed
    # ----------------------------------------------------------------------
    # The common card renders always-on fields + a collapsed <details>. Rather
    # than compute the full change feed for every card up front (a roster can be
    # 40+ players, one mail-tracking audit each), the list surfaces run ONE
    # batched presence query and lazy-load the full feed only for cards the user
    # actually opens (see the /my/player/<id>/recent-changes route + the
    # portal_card_recent_changes.js toggle listener).

    @api.model
    def _dashboard_player_fields(self, role):
        """Patient-level tracked field set for ``role`` (Law-25 gate)."""
        player_fields = set(external_tracking_fields)
        if role == "tp":
            player_fields |= set(internal_tracking_fields)
        return player_fields

    @api.model
    def _dashboard_injury_field_set(self, role):
        """Injury-level tracked field set for ``role`` (Law-25 gate)."""
        injury_fields = set(dashboard_external_injury_fields)
        if role == "tp":
            injury_fields |= set(dashboard_internal_injury_fields)
        return injury_fields

    @api.model
    def _dashboard_visible_injuries(self, patients, role):
        """All injuries of ``patients`` the ``role`` may see. Read sudo (portal
        coaches cannot read the audit trail), so the Law-25 gate is applied HERE
        and nowhere later: a coach never gets a hidden-from-coaches injury.
        """
        injuries = patients.sudo().injury_ids
        if role == "coach":
            injuries = injuries.filtered(lambda i: not i.hidden_from_coaches)
        return injuries

    @api.model
    def _dashboard_tracking_old_values(self, res_model, records, cutoff):
        """ONE batched mail-tracking read for ALL ``records`` (task 1387).

        Returns ``{res_id: {field_name: raw_old_display_value}}`` where the value
        is the PRE-WINDOW one — the OLDEST in-window tracking for that field, so
        old-vs-current reads as the NET delta over the window rather than each
        intermediate hop. Exactly one ``mail.message`` search regardless of how
        many records are passed; that is the whole point (a team dashboard
        renders up to ~70 cards and must not audit them one at a time).
        """
        res_ids = [r for r in (records.ids if records else []) if r]
        if not res_ids:
            return {}
        model_fields = self.env[res_model]._fields
        messages = self.env["mail.message"].sudo().search(
            [
                ("model", "=", res_model),
                ("res_id", "in", res_ids),
                ("date", ">=", cutoff),
            ],
            order="date asc, id asc",
        )
        olds = {}
        for msg in messages:
            per_record = olds.setdefault(msg.res_id, {})
            for tracking in msg.tracking_value_ids:
                fname = tracking.field_id.name
                if fname in per_record:
                    continue  # oldest wins -> that is the pre-window value
                field = model_fields.get(fname)
                if field is None:
                    continue
                per_record[fname] = tracking._format_display_value(
                    field.type, new=False)[0]
        return olds

    @api.model
    def _dashboard_net_changed_fields(self, record, old_values, allowed_fields):
        """Names among ``allowed_fields`` that NET-changed on ``record``, given
        the batched ``{field_name: raw_old}`` map from
        ``_dashboard_tracking_old_values``. Pure in-memory: applies the SAME
        shared rule the change feed uses (``_dashboard_is_net_change``), so a
        round-trip or a language-only difference contributes nothing.
        """
        changed = set()
        for fname, raw_old in (old_values or {}).items():
            if fname not in allowed_fields or fname not in record._fields:
                continue
            old = self._dashboard_normalize_old_value(record, fname, raw_old)
            if self._dashboard_is_net_change(record, fname, old):
                changed.add(fname)
        return changed

    @api.model
    def _dashboard_injury_presence_from_olds(self, injuries, role, injury_olds):
        """In-memory half of the injury presence: ids of ``injuries`` with at
        least one NET-changed dashboard field. Split out so the card presence can
        reuse the single batched read instead of issuing a second one."""
        injury_fields = self._dashboard_injury_field_set(role)
        return {
            injury.id for injury in injuries
            if self._dashboard_net_changed_fields(
                injury, injury_olds.get(injury.id), injury_fields)
        }

    @api.model
    def _dashboard_injury_presence(self, patients, role, cutoff=None):
        """ONE batched audit read across ALL given patients' injuries: the set of
        injury ids whose dashboard-tracked fields changed within the window.

        Drives the "recent change" marker on the static active-injury entries of
        the portal card. Ids only — never rendered items. ``role`` is the Law-25
        gate: a coach never gets a hidden-from-coaches injury in the set.

        Task 1387: "changed" now means NET changed. A field that round-trips
        within the window (or whose tracking differs only by the writer's
        language) no longer contributes an id, so the marker cannot appear over
        an entry the expanded feed has nothing to say about.
        """
        if cutoff is None:
            cutoff = self._dashboard_window_cutoff()
        injuries = self._dashboard_visible_injuries(patients, role)
        if not injuries:
            return set()
        injury_olds = self._dashboard_tracking_old_values(
            "sports.patient.injury", injuries, cutoff)
        return self._dashboard_injury_presence_from_olds(
            injuries, role, injury_olds)

    @api.model
    def _dashboard_card_presence(self, patients, role, cutoff=None):
        """Batched presence for the portal cards. Returns
        ``{'players': set(patient_ids), 'injuries': set(injury_ids)}``.

        - ``players`` drives the « changements récents » pill on the collapsed
          control AND the lazy-load container behind it.
        - ``injuries`` drives the static active-injury section markers.

        Task 1387 — the pill is no longer a stored-stamp lookup. The stamp is
        bumped by ANY tracked write, including one that nets to nothing, so the
        pill could announce a feed that renders empty. Both sets are now derived
        from the SAME change data (and the same net-no-op rule) as the feed the
        card lazy-loads, so a pill appears if and only if that feed has content:

          player is flagged  <=>  ``_dashboard_change_items_deduped`` is non-empty

        which means a net-changed patient-level tracked field, OR a note update
        in the window, OR a net-changed field on an injury the card does NOT show
        up top (an active injury's own field changes are de-duped out of the feed
        — they are marked in the static section instead).

        PERFORMANCE — this is a BATCHED computation: exactly two ``mail.message``
        searches (patients + injuries) and one note-history search for the WHOLE
        recordset, then pure in-memory comparison. It must never become a
        per-player loop over ``_dashboard_change_items``: the largest production
        team has 67 players on one page.

        The stored ``dashboard_last_activity_<role>`` stamp is untouched and its
        other consumers (the dashboard-tab recency filter, the morning briefing's
        change count) keep using it.
        """
        if cutoff is None:
            cutoff = self._dashboard_window_cutoff()
        patients = patients.sudo()

        # --- 1. ONE batched injury audit read, reused by both sets.
        injuries = self._dashboard_visible_injuries(patients, role)
        injury_olds = self._dashboard_tracking_old_values(
            "sports.patient.injury", injuries, cutoff)
        changed_injuries = self._dashboard_injury_presence_from_olds(
            injuries, role, injury_olds)

        # --- 2. ONE batched patient-level audit read.
        player_olds = self._dashboard_tracking_old_values(
            "sports.patient", patients, cutoff)
        player_fields = self._dashboard_player_fields(role)

        # --- 3. ONE batched note-history read (notes are never de-duped out of
        #        the feed, so any in-window note update means content).
        note_domain = [
            ("patient_id", "in", patients.ids),
            ("note_datetime", ">=", cutoff),
        ]
        if role == "coach":
            note_domain += [
                ("scope", "=", "external"),
                ("injury_id.hidden_from_coaches", "=", False),
            ]
        histories = self.env["sports.injury.note.history"].sudo().search(
            note_domain)
        noted_patients = set()
        for hist in histories:
            injury = hist.injury_id
            if not injury:
                continue
            if role == "coach" and injury.hidden_from_coaches:
                continue
            note_field = (
                "external_notes" if hist.scope == "external" else "internal_notes"
            )
            if note_field in injury._fields and injury[note_field]:
                noted_patients.add(hist.patient_id.id)

        # --- 4. In-memory fold, mirroring _dashboard_change_items_deduped.
        changed_players = set()
        for patient in patients:
            if patient.id in noted_patients:
                changed_players.add(patient.id)
                continue
            if self._dashboard_net_changed_fields(
                    patient, player_olds.get(patient.id), player_fields):
                changed_players.add(patient.id)
                continue
            for injury in patient.injury_ids:
                if injury.id not in changed_injuries:
                    continue
                if injury.stage == "active":
                    # Shown in the card's static section -> its field changes are
                    # de-duped OUT of the feed (marked up top instead).
                    continue
                if injury.create_date and injury.create_date >= cutoff:
                    # A brand-new injury emits no change-feed unit (task 1385).
                    continue
                changed_players.add(patient.id)
                break

        return {
            "players": changed_players,
            "injuries": changed_injuries,
        }

    def _dashboard_change_items_deduped(self, role, cutoff, shown_injury_ids):
        """The change feed for one player with the injury de-dup applied.

        The card's static top section shows each active injury's DETAIL fields
        (diagnosis, body location, type/severity/stage, dates) with a "recent
        change" marker when they changed — so repeating those field-changes in
        the recent-changes list is redundant. We therefore drop only the
        detail-field change items (category ``injury``) of injuries shown up top.
        Everything else stays: player-level status changes, note updates (notes
        are NOT shown in the static section), new-injury units, and any change on
        an injury NOT displayed up top (e.g. a resolved injury).
        """
        self.ensure_one()
        shown = set(shown_injury_ids or [])
        items = []
        for it in self._dashboard_change_items(role, cutoff):
            injury = it.get("injury")
            if (
                it.get("category") == "injury"
                and injury and injury.id in shown
            ):
                continue
            items.append(it)
        return items

    def _card_injury_detail(self, injury, cutoff=None):
        """JSON-safe detail dict for one injury, shared by the LIVE card and the
        frozen snapshot so both render an identical static injury block.

        ``cutoff`` (defaults to the live window) flags a freshly reported injury
        as ``is_new`` (task 1385, CR-A #5): a new injury is marked "Nouvelle"
        up top in the static section instead of emitting a redundant
        "Nouvelle blessure …" change-feed row."""
        if cutoff is None:
            cutoff = self._dashboard_window_cutoff()
        def _sel_label(field_name):
            field = injury._fields.get(field_name)
            if not field or not injury[field_name]:
                return ""
            try:
                selection = dict(field._description_selection(injury.env))
            except Exception:  # pragma: no cover - defensive
                raw = getattr(field, "selection", None)
                selection = dict(raw) if isinstance(raw, (list, tuple)) else {}
            return str(selection.get(injury[field_name], injury[field_name]))

        return {
            "injury_id": injury.id,
            "diagnosis": injury.diagnosis or "",
            "body_location": injury.body_location or "",
            "injury_type": injury.injury_type or "",
            "severity": _sel_label("severity"),
            "stage": _sel_label("stage"),
            "injury_date": (
                fields.Date.to_string(injury.injury_date)
                if injury.injury_date else ""
            ),
            "predicted_resolution_date": (
                fields.Date.to_string(injury.predicted_resolution_date)
                if injury.predicted_resolution_date else ""
            ),
            "resolution_date": (
                fields.Date.to_string(injury.resolution_date)
                if injury.resolution_date else ""
            ),
            "hidden_from_coaches": bool(injury.hidden_from_coaches),
            "is_new": bool(
                injury.create_date and cutoff and injury.create_date >= cutoff
            ),
            # Task 1385 (CR-D2): surface the injury's notes in the static
            # active-injury section. This dict is the TP superset (both scopes);
            # audience-scoping — coach sees external only, TP sees internal +
            # external — is applied by the caller (``_card_active_injuries`` for
            # the live card; ``_render_for_role`` for the frozen snapshot), never
            # leaking internal notes to a coach.
            "external_notes": injury.external_notes or "",
            "internal_notes": injury.internal_notes or "",
        }

    def _card_active_injuries(self, is_treatment_prof=True):
        """Active-injury detail dicts for the LIVE card's static section. Read as
        the current portal user, so the coach record rule already hides
        ``hidden_from_coaches`` injuries — no extra injury-level filtering needed.

        Task 1385 (CR-D2): ``internal_notes`` are FIELD-level restricted (a coach
        may still read a non-hidden injury's record), so the flag drops the
        internal note from the coach's dict here — the same audience-scope the
        change feed and snapshot enforce. TP/admin keep both note scopes."""
        self.ensure_one()
        details = []
        for inj in self.injury_ids.filtered(lambda i: i.stage == "active"):
            detail = self._card_injury_detail(inj)
            if not is_treatment_prof:
                detail["internal_notes"] = ""
            details.append(detail)
        return details

    @api.model
    def _dashboard_note_count_label(self, count):
        """Bare '<n> new note(s)' phrase (no surrounding parens), pluralised.
        Wrapped in parens by the caller when folded into a longer phrase."""
        if count == 1:
            return _("%s new note", count)
        return _("%s new notes", count)

    def _dashboard_change_synopsis(self, role, cutoff=None, items=None):
        """Ordered list of short, per-category synopsis phrases for the
        COLLAPSED digest card (task 1272, condense round 2).

        Built from the SAME role-scoped ``_dashboard_change_items`` list as the
        expanded view — never from raw records — so a coach synopsis can no more
        name a hidden injury or an internal note than the coach digest can: the
        items it reads are already visibility-filtered. This is PRESENTATION
        ONLY; it changes no detection, tracking set, or scoping. The caller joins
        the phrases into the ≤2-3 line collapsed summary (the list is capped +
        folded here so the busiest player never wraps into an article again).
        """
        self.ensure_one()
        if items is None:
            items = self._dashboard_change_items(role, cutoff=cutoff)
        if not items:
            return []
        phrases = []
        # 1. New injuries no longer appear in the synopsis (task 1385, CR-A #5):
        #    they are flagged in the static card section, not the change feed, so
        #    their notes fold into the plain note count in step 4 like any other.
        # 2. Player-level status changes.
        status_fields = {
            it["field"] for it in items if it.get("category") == "status"}
        if {"match_status", "practice_status"} & status_fields:
            phrases.append(_("Status changed"))
        if "training_recommendation" in status_fields:
            phrases.append(_("Training recommendation updated"))
        # Other tracked player fields — explicit translatable phrases so the
        # synopsis stays fully localized (the raw field label is often English
        # only, and "%s updated" gets the French agreement wrong). Falls back to
        # "<label> updated" for any unmapped tracked field.
        handled = {"match_status", "practice_status", "training_recommendation"}
        field_phrases = {
            "predicted_return_date": _("Predicted return updated"),
            "return_date": _("Return date updated"),
            "last_consultation_date": _("Last consultation updated"),
            "team_info_notes": _("Team notes updated"),
            "age": _("Age updated"),
            "date_of_birth": _("Date of birth updated"),
        }
        for it in items:
            if it.get("category") == "status" and it["field"] not in handled:
                phrases.append(
                    field_phrases.get(it["field"]) or _("%s updated", it["label"]))
        # 3. Updated (existing) injuries — one phrase per injury, deduped, with
        #    diagnosis (note changes on them are folded as a count in step 4).
        seen_injuries = set()
        for it in items:
            if it.get("category") != "injury":
                continue
            injury = it.get("injury")
            key = injury.id if injury else it.get("field")
            if key in seen_injuries:
                continue
            seen_injuries.add(key)
            diag = (injury.diagnosis or "").strip() if injury else ""
            phrases.append(
                _("Injury updated (%s)", diag) if diag else _("Injury updated"))
        # 4. Note changes on EXISTING injuries — folded into one count,
        #    scope-appropriate (the items list is already coach: external only /
        #    TP: internal + external).
        note_count = sum(1 for it in items if it.get("category") == "note")
        if note_count:
            phrases.append(self._dashboard_note_count_label(note_count))
        # Cap + fold so the collapsed card stays ≤2-3 lines.
        if len(phrases) > DASHBOARD_SYNOPSIS_MAX_PHRASES:
            extra = len(phrases) - DASHBOARD_SYNOPSIS_MAX_PHRASES
            phrases = phrases[:DASHBOARD_SYNOPSIS_MAX_PHRASES]
            phrases.append(_("+%s more changes", extra))
        return phrases

    @api.depends(
        "dashboard_last_activity_tp",
        "dashboard_score_tp",
        "injury_ids",
        "injury_ids.note_history_ids",
    )
    def _compute_dashboard_digest_html(self):
        """Render the TP-scoped digest for the backend kanban via the shared
        QWeb fragment. Non-stored: recomputed per read so the window applies
        live. Backend team Dashboard tab audience is internal staff = TP."""
        cutoff = self._dashboard_window_cutoff()
        show_position = bool(self.env.context.get("dashboard_show_position"))
        for rec in self:
            items = rec._dashboard_change_items("tp", cutoff)
            # Task 1385 (CR-A #5 / CR-B): the internal digest also drops the
            # "Nouvelle blessure …" feed row, so surface the standing active
            # injuries (new ones flagged) in a static block, matching the card.
            changed_injuries = self._dashboard_injury_presence(rec, "tp", cutoff)
            active_injuries = rec._card_active_injuries()
            for inj in active_injuries:
                inj["changed"] = inj["injury_id"] in changed_injuries
            rec.dashboard_digest_html = self.env["ir.qweb"]._render(
                "bemade_sports_clinic.dashboard_change_items",
                {
                    "items": items,
                    # Same role-scoped items -> the collapsed synopsis on the
                    # backend card is Law-25 safe by construction.
                    "synopsis": rec._dashboard_change_synopsis("tp", items=items),
                    "show_position": show_position,
                    "position": rec.position,
                    # Task 1381: internal card only — an always-on player-status
                    # block (predicted return + training recommendation) rendered
                    # ahead of the changelog, pulled live from the record. The
                    # flag keeps it off the shared portal renders (that's #1385).
                    "show_player_status": True,
                    "predicted_return_date": rec.predicted_return_date,
                    "training_recommendation": rec.training_recommendation,
                    "active_injuries": active_injuries,
                },
            )

    def _sync_date_left_last_team(self):
        """Maintain the Law 25 retention clock on every path that can change a
        player's roster membership.

        **I1 — teamless ⇔ ``date_left_last_team`` set.** Stamp the field when a
        player becomes teamless (and isn't already stamped — so the sanity
        backfill of an already-teamless, unset record also lands on today), and
        clear it when the player (re)joins a team. The Law 25 retention rule keys
        on this date: a NULL clock never surfaces for anonymization, and a stale
        one ages the record out years early.

        This helper does NOT archive anyone. Auto-archiving players who leave
        their last team was tried and dropped (owner, 2026-07-16): most teamless
        players are simply between seasons awaiting re-rostering, not departed —
        on prod that was 367 active teamless players, not the handful expected.
        Archiving stays a manual action plus the Law 25 anonymization; the
        retention clock is the only teamless state tracked automatically here.

        Callers must pass the players read with ``active_test=False`` where an
        archived-but-rostered player could otherwise be skipped (the team-side
        paths do this via ``sports.team._roster``): an archived player on a
        roster is an allowed state, and their clock must still be maintained.
        """
        today = fields.Date.context_today(self)
        for patient in self:
            # I1 — teamless ⇔ date set
            if not patient.team_ids and not patient.date_left_last_team:
                patient.date_left_last_team = today
            elif patient.team_ids and patient.date_left_last_team:
                patient.date_left_last_team = False

    def _recompute_name(self):
        for rec in self:
            rec.partner_id.with_context(patient_update=True).name = (
                rec._get_name_from_first_and_last(rec.first_name, rec.last_name)
            )

    # ----------------------------------------------------------------------
    # Law 25 retention anonymization
    # ----------------------------------------------------------------------
    def _law25_anonymize(self):
        """Irreversibly anonymize a player's core identity PII on BOTH the
        ``sports.patient`` and its ``res.partner``.

        Driven by the ``data_recycle`` retention engine's *anonymize* action
        after an admin validates the review candidate. Idempotent: an already
        anonymized record is skipped. PHI on linked clinical records
        (injuries, treatment notes, ...) is out of scope for this phase.
        """
        for patient in self:
            if patient.is_anonymized:
                continue
            patient = patient.sudo()
            partner = patient.partner_id
            # Overwrite stored PII on the patient. Tracking is disabled so the
            # anonymizing write itself does not log the old values, and
            # first/last are overwritten so partner.name does not recompose to
            # the real identity via _recompute_name.
            patient.with_context(
                tracking_disable=True,
                mail_create_nolog=True,
            ).write(
                {
                    "first_name": _("Anonymized"),
                    "last_name": _("Player %s") % patient.id,
                    "date_of_birth": False,
                    "team_info_notes": False,
                    "predicted_return_date": False,
                    "return_date": False,
                    "is_anonymized": True,
                }
            )
            # Overwrite core identity PII on the partner (address, email, ...).
            if partner:
                partner._law25_anonymize()
            # Purge residual PII from each record's OWN chatter/tracking, else
            # anonymization is self-defeating (old values still in history).
            self._law25_scrub_mail_history(patient)
            if partner:
                self._law25_scrub_mail_history(partner)
            # Audit note (restates no old PII) on each anonymized record.
            audit_body = _(
                "Personal data anonymized under the Law 25 retention policy "
                "on %s."
            ) % fields.Date.to_string(fields.Date.today())
            patient.with_context(
                tracking_disable=True, mail_create_nosubscribe=True
            ).message_post(body=audit_body)
            if partner:
                partner.sudo().with_context(
                    tracking_disable=True, mail_create_nosubscribe=True
                ).message_post(body=audit_body)

    def _law25_scrub_mail_history(self, records):
        """Delete chatter messages, tracking values and followers on the given
        mail.thread records so no residual PII survives anonymization.

        Scope = the anonymized records' OWN threads. Cross-object references
        elsewhere are handled by the phase-2 PHI de-identification task.
        """
        Message = self.env["mail.message"].sudo()
        Tracking = self.env["mail.tracking.value"].sudo()
        for record in records:
            messages = Message.search(
                [("model", "=", record._name), ("res_id", "=", record.id)]
            )
            if messages:
                # mail.tracking.value cascades on message unlink, but purge
                # explicitly for clarity and to be robust to ordering.
                Tracking.search(
                    [("mail_message_id", "in", messages.ids)]
                ).unlink()
                messages.unlink()
            followers = record.sudo().message_follower_ids
            if followers:
                followers.unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for row in vals_list:
            if "partner_id" not in row:
                row["partner_id"] = (
                    self.env["res.partner"].with_context(
                        tracking_disable=True,
                        mail_create_nosubscribe=True,
                    )
                    .create(
                        {
                            "name": self._get_name_from_first_and_last(
                                row["first_name"], row["last_name"]
                            )
                        }
                    )
                    .id
                )
        res = super().create(vals_list)
        # Stamp the Law 25 retention clock for any player created without a team.
        res._sync_date_left_last_team()
        # Avoid triggering follower recomputation (which can create mail/follower
        # side-effects) when explicitly asked to skip, e.g., during portal creation.
        if not self.env.context.get("skip_recompute_followers"):
            res.sudo().with_context(
                tracking_disable=True,
                mail_create_nosubscribe=True,
            ).recompute_followers()
        return res

    @api.constrains("match_status", "practice_status")
    def constrain_match_and_practice_status(self):
        """Avoid invalid combinations of match and practice status:
        - Yes (match), No (practice)
        - Yes (match), No Contact (practice)
        """
        # combinations of (match_status, practice_status) that are valid
        valid_combinations = [
            ("yes", "yes"),
            ("no", "yes"),
            ("no", "no_contact"),
            ("no", "no"),
        ]
        for rec in self:
            if (rec.match_status, rec.practice_status) not in valid_combinations:
                raise ValidationError(
                    _("Invalid combination of match and practice status.")
                )

    @api.depends("injury_ids.stage")
    def _compute_active_injury_count(self):
        for rec in self:
            rec.active_injury_count = len(
                rec.injury_ids.filtered(lambda r: r.stage == "active")
            )

    @api.depends("match_status", "practice_status")
    def _compute_stage(self):
        stage_map = {
            ("yes", "yes"): "healthy",
            ("no", "yes"): "practice_ok",
            ("no", "no_contact"): "practice_ok",
            ("no", "no"): "no_play",
        }
        for rec in self:
            # not a valid combination, will be caught by constraint if save is attempted
            if (rec.match_status, rec.practice_status) not in stage_map:
                rec.stage = False
                continue
            rec.stage = stage_map[(rec.match_status, rec.practice_status)]

    @api.depends("match_status", "practice_status")
    def _compute_sort_order(self):
        # Stored status-severity key driving roster ordering on the backend
        # team-form Players list and the portal roster. Depends on the same
        # stored roots as `stage` (a non-stored computed), so reading
        # `self.stage` here is safe: any change to match/practice status
        # recomputes `stage` and this field together.
        severity = {"no_play": 0, "practice_ok": 1, "healthy": 2}
        for rec in self:
            rec.sort_order = severity.get(rec.stage, 99)

    @api.depends("date_of_birth")
    def _compute_age(self):
        for rec in self:
            if not rec.date_of_birth:
                rec.age = False
            else:
                rec.age = relativedelta(date.today(), rec.date_of_birth).years

    @api.model
    def _get_name_from_first_and_last(self, first_name, last_name):
        names = []
        if first_name:
            names.append(first_name)
        if last_name:
            names.append(last_name)
        return " ".join(names)

    # ----------------------------------------------------------------------
    # Portal « Last, First » display + picker helpers (task 1414)
    # ----------------------------------------------------------------------
    # The portal LISTS (clinic worklist, patient cards) and every patient
    # PICKER read and sort « Last, First » straight from the patient record
    # (last_name / first_name — never res.partner.name, which is
    # « First Last »). Single-patient headings (player page H1, clinic dossier
    # header, breadcrumbs) keep « First Last » via ``name``.
    @staticmethod
    def _portal_name_key(text):
        """Accent-insensitive, case-insensitive sort / search key of a name
        part: NFKD-decomposed, combining marks dropped, casefolded, inner
        whitespace collapsed. « Zoé Äbel » → « zoe abel »."""
        decomposed = unicodedata.normalize("NFKD", (text or "").strip())
        stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
        return " ".join(stripped.casefold().split())

    def _portal_list_name(self):
        """« Last, First » of ONE patient for portal lists and pickers.

        Graceful when a part is empty (the other part alone; ``name`` as a
        last resort so an anonymized / legacy record never renders blank).
        """
        self.ensure_one()
        last = (self.last_name or "").strip()
        first = (self.first_name or "").strip()
        if last and first:
            return "%s, %s" % (last, first)
        return last or first or (self.name or "")

    def _portal_combo_key(self):
        """Normalized « last first » search key of ONE patient (what the
        portal combo filters on, client-side, from the rendered options)."""
        self.ensure_one()
        return " ".join(
            part for part in (
                self._portal_name_key(self.last_name),
                self._portal_name_key(self.first_name),
            ) if part
        )

    def _portal_combo_sorted(self):
        """This recordset ordered by last name, then first name — accent and
        case insensitive, ties broken by id — regardless of the incoming
        order (``_order`` puts sort_order / injury severity first, which is
        right for the lists but wrong for a picker)."""
        return self.sorted(key=lambda p: (
            p._portal_name_key(p.last_name), p._portal_name_key(p.first_name), p.id))

    def _portal_combo_options(self):
        """``[(id, « Last, First », search_key)]`` for the portal patient combo
        (views/portal_widgets_templates.xml), ordered by last name, first
        name. Pure read of the records already in hand — no search, so the
        combo can only ever offer what the page already renders."""
        return [
            (p.id, p._portal_list_name(), p._portal_combo_key())
            for p in self._portal_combo_sorted()
        ]

    @api.depends("practice_status", "match_status", "injury_ids.injury_date")
    def _compute_is_injured(self):
        for patient in self:
            # Patient is injured if their stage is not "healthy"
            patient.is_injured = patient.stage != "healthy"
            
            # For injured_since, find the earliest injury date from active injuries
            # This logic is kept but may not be reliable until user habits change
            if patient.is_injured:
                active_injuries = self.env["sports.patient.injury"].search(
                    [
                        ("patient_id", "=", patient.id),
                        ("stage", "=", "active"),
                    ]
                )
                if active_injuries:
                    injury_dates = [d for d in active_injuries.mapped("injury_date") if d]
                    patient.injured_since = min(injury_dates) if injury_dates else False
                else:
                    patient.injured_since = False
            else:
                patient.injured_since = False
                
    def _compute_treatment_note_count(self):
        for patient in self:
            patient.treatment_note_count = self.env['sports.treatment.note'].search_count(
                [('patient_id', '=', patient.id)]
            )

    def _compute_activity_count(self):
        for rec in self:
            rec.activity_count = self.env['mail.activity'].search_count([
                ('res_model', '=', 'sports.patient'),
                ('res_id', '=', rec.id)
            ])

    def _compute_document_count(self):
        for patient in self:
            patient.document_count = self.env['sports.injury.document'].search_count([
                ('patient_id', '=', patient.id)
            ])

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'sports.injury.document',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {
                'default_patient_id': self.id,
            },
        }

    def action_view_patient_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "sports.patient",
            "res_id": self.id,
            "context": self.env.context,
        }

    def action_consulted_today(self):
        self.ensure_one()  # should just be called from form view
        self.last_consultation_date = fields.Date.context_today(self)
        return {
            "view_mode": "form",
            "res_model": "sports.patient",
            "context": self.env.context,
            "res_id": self.id,
        }
        
    def action_report_injury(self):
        """Public method to report injury with proper access checks."""
        self.ensure_one()
        
        # Check permissions - user must have access to this patient
        user = self.env.user
        if user.has_group('base.group_portal'):
            # Portal users must be staff on at least one of the patient's teams
            user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
            patient_teams = self.team_ids
            if not (user_teams & patient_teams):
                raise AccessError(_("You don't have permission to report injuries for this patient"))
        # Backend users with appropriate groups can access any patient
        elif not (user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional') or
                  user.has_group('bemade_sports_clinic.group_sports_clinic_admin') or
                  user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to report injuries"))
        
        # Call the private implementation
        return self._action_report_injury()
    
    def _action_report_injury(self):
        """
        Private method containing the actual sudo operations for injury reporting.
        
        :return: dict: Action result with success notification
        """
        self.ensure_one()
        is_portal = self.env.user.has_group('base.group_portal')
        
        if is_portal:
            # Redirect to portal injury form
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            portal_url = f"{base_url}/my/patient/injury/new?patient_id={self.id}"
            return {
                'type': 'ir.actions.act_url',
                'url': portal_url,
                'target': 'self',
            }
        else:
            # Open backend injury form
            return {
                'type': 'ir.actions.act_window',
                'name': f'Report Injury for {self.name}',
                'view_mode': 'form',
                'res_model': 'sports.patient.injury',
                'context': {
                    'default_patient_id': self.id,
                    'default_patient_name': self.name,
                    'default_stage': 'active',
                    'default_team_id': self.team_ids[0].id if self.team_ids else False
                },
            }

    @api.onchange("phone", "country_id")
    def _onchange_phone_validation(self):
        if self.phone:
            self.phone = self._phone_format(self.phone, force_format="INTERNATIONAL")

    def _phone_format(self, number, force_format="E164"):
        country = self.country_id or self.env.company.country_id
        if not country or not number:
            return number
        return phone_validation.phone_format(
            number,
            country.code if country else None,
            country.phone_code if country else None,
            force_format=force_format,
            raise_exception=False,
        )

    def _track_subtype(self, init_values):
        return self.env.ref("mail.mt_note")

    def _track_template(self, changes):
        res = super()._track_template(changes)
        # Task 1269: the per-change play-status email is replaced by the
        # aggregated urgent-notification cron + dashboard/digest. Keep the
        # tracking/chatter audit log (recorded by super()) but only attach the
        # notifying template when the legacy flag is explicitly enabled.
        if not legacy_change_emails_enabled(self.env):
            return res
        params = set(changes)
        external = bool(external_tracking_fields & params)
        if external:
            first_external_field = (external_tracking_fields & params).pop()
            res[first_external_field] = (
                self.env.ref(
                    "bemade_sports_clinic.mail_template_patient_status_update"
                ),
                {
                    "auto_delete": False,
                    "subtype_id": self.env.ref(
                        "bemade_sports_clinic.subtype_patient_external_update"
                    ).id,
                    "email_layout_xmlid": "mail.mail_notification_light",
                },
            )
        # Tracking removed from team_info_notes HTML field as it's not supported by the mail tracking system
        # if "team_info_notes" in changes:
        #     res["team_info_notes"] = (
        #         self.env.ref(
        #             "bemade_sports_clinic.mail_template_patient_new_team_note"
        #         ),
        #         {
        #             "auto_delete": False,
        #             "subtype_id": self.env.ref(
        #                 "bemade_sports_clinic.subtype_patient_internal_update"
        #             ).id,
        #             "email_layout_xmlid": "mail.mail_notification_light",
        #         },
        #     )
        return res
        
    def _get_team_head_therapist_user(self, team):
        """Get the head therapist user for a team, or None if not found"""
        head_therapist = team.staff_ids.filtered(
            lambda s: s.role == 'head_therapist' and s.user_ids
        )
        if head_therapist:
            return head_therapist.user_ids[0]
        return None
        
    def _get_admin_user(self):
        """Get the admin user with the lowest ID"""
        return self.env['res.users'].search([('active', '=', True)], order='id', limit=1)
    
    def request_team_removal(self, team_id, reason=None):
        """Public method to request team removal with proper access checks."""
        self.ensure_one()
        team = self.env['sports.team'].browse(team_id)
        
        # Get current user and check permissions
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system')
        
        # Permission check - do this before team membership validation
        if not is_admin:
            # Check if user is staff on the team
            user_staff_roles = team.staff_ids.filtered(
                lambda s: s.user_ids and current_user.id in s.user_ids.ids
            )
            if not user_staff_roles:
                raise AccessError(_(
                    "You don't have permission to request removal for this team. "
                    "Only team staff or administrators can request player removal."
                ))
        
        # Validate team existence and membership
        if not team.exists():
            raise ValidationError(_("Team not found or you don't have access to it"))
            
        if team not in self.team_ids:
            raise ValidationError(_("Player is not a member of the specified team"))
        
        # Call the private implementation
        return self._request_team_removal(team_id, reason)
    
    def _request_team_removal(self, team_id, reason=None):
        """
        Private method containing the actual sudo operations for requesting team removal.
        The actual activity creation will be handled by the scheduled action.
        
        :param int team_id: ID of the team to request removal from
        :param str reason: Optional reason for the removal request
        :return: dict: Action result with success notification
        """
        self.ensure_one()
        team = self.env['sports.team'].browse(team_id)
        current_user = self.env.user
        
        # Set the pending_removal flag
        self.write({'pending_removal': True})
        
        # Log the request with details
        log_message = _(
            "Removal request submitted for player %(player)s from team %(team)s by %(user)s"
        ) % {
            'player': self.display_name,
            'team': team.name,
            'user': current_user.name
        }
        
        if reason:
            log_message += _("\nReason: %s") % reason
            
        # Log the request in the chatter
        self.sudo().message_post(body=log_message)
        
        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Removal Request Submitted'),
                'message': _('Your removal request has been submitted and will be processed by an administrator.'),
                'type': 'success',
                'sticky': True,
            }
        }
        
    def _schedule_removal_request_activity(self, request_data):
        """
        Scheduled action to create an activity for the head therapist to review the removal request.
        
        :param dict request_data: Data for the removal request
        """
        player = self.env['sports.patient'].browse(request_data['player_id'])
        team = self.env['sports.team'].browse(request_data['team_id'])
        requested_by = self.env['res.users'].browse(request_data['requested_by_id'])
        reason = request_data['reason']
        is_last_team = request_data['is_last_team']
        assignee = self.env['res.users'].browse(request_data['assignee_id'])
        
        # Create a more detailed activity
        note = _("Player Removal Request\n")
        note += _("====================\n\n")
        note += _("Player: %s\n") % player.display_name
        note += _("Team: %s\n") % team.name
        note += _("Requested by: %s\n\n") % requested_by.name
        
        if reason:
            note += _("Reason for removal request:\n%s\n\n") % reason
            
        if is_last_team:
            note += _("⚠️ WARNING: This is the player's only team. Removing it will leave the player with no team.\n\n")
            
        note += _("Please review this request and take appropriate action.")
        
        # Create activity for head therapist
        activity_vals = {
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'note': note,
            'res_id': player.id,
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'user_id': assignee.id,
            'summary': _('Player Removal Request: %s') % player.display_name,
        }
        
        # Create the activity
        self.env['mail.activity'].create(activity_vals)
    

    
    @api.model
    def _cron_handle_pending_removals(self):
        """
        Scheduled action to handle players pending removal.
        Creates mail activities for head therapists to review the removal requests.
        """
        # Find all active players with pending removal that still have teams
        players_pending_removal = self.search([
            ('active', '=', True),
            ('pending_removal', '=', True),
            ('team_ids', '!=', False)
        ])
        
        if not players_pending_removal:
            return
            
        # Get the mail activity type
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        model_id = self.env['ir.model']._get('sports.patient').id
        today = fields.Date.today()
        
        for player in players_pending_removal:
            # Skip if there's already an activity for this player
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'sports.patient'),
                ('res_id', '=', player.id),
                ('activity_type_id', '=', activity_type.id),
                ('summary', 'ilike', 'Player Removal Request')
            ], limit=1)
            
            if existing_activity:
                continue
                
            # Find head therapist (role == 'head_therapist') or fallback to any therapist
            team = player.team_ids[0]
            staff = team.staff_ids
            head_therapist = staff.filtered(lambda s: s.role == 'head_therapist' and s.user_ids)
            if not head_therapist:
                # Fallback to any therapist with a linked user
                head_therapist = staff.filtered(lambda s: s.role == 'therapist' and s.user_ids)

            user_id = SUPERUSER_ID
            if head_therapist:
                # pick first linked user id
                user_id = head_therapist.user_ids[0].id
            
            # Create the activity
            self.env['mail.activity'].create({
                'activity_type_id': activity_type.id,
                'summary': _('Player Removal Request'),
                'note': _('Player %s has been requested for removal from the team. Please review.') % player.display_name,
                'user_id': user_id,
                'res_id': player.id,
                'res_model_id': model_id,
                'date_deadline': today,
            })
    
    def _removal_log_message(self, team_name, user_name):
        """Compose the chatter line describing a removal from ``team_name``.

        Call AFTER the roster write — the wording depends on whether the player
        was left teamless.

        Formerly ``_archive_if_no_teams``, which returned a
        ``(should_archive, message)`` tuple and, despite its name, archived
        nothing: the caller only ever used the tuple to pick a log line. Our code
        no longer archives players on removal at all, so all that is left here is
        the message.

        :param str team_name: Name of the team the patient was removed from
        :param str user_name: Name of the user performing the action
        :return: str: the chatter line
        """
        self.ensure_one()
        if not self.team_ids:
            return _("Removed from last team %s. The player now has no team.") % team_name
        return _("Removed from team %s by %s") % (team_name, user_name)

    def _may_remove_from_team(self, team):
        """Single source of truth for "may the current user directly remove a
        player from ``team``?" — shared by BOTH the internal recordset
        ``remove_from_team`` and the portal ``portal_remove_player`` route, so
        the two paths can never drift apart again (task 1260).

        Policy:
        - ``base.group_system`` may remove any player, regardless of role; OR
        - the user holds EITHER treatment-professional group AND has a staff row
          on THIS team with ``role in REMOVAL_ROLES`` (therapist / head
          therapist). Everyone else (coaches, doctors, non-staff) must use the
          Request Removal flow.

        BOTH treatment-professional groups are accepted on purpose.
        ``group_portal_treatment_professional`` and
        ``group_sports_clinic_treatment_professional`` are DISJOINT — the portal
        group implies only ``base.group_portal``, never the internal group, and
        the internal group is held only via ``group_sports_clinic_admin``. A
        portal therapist therefore holds ONLY the portal group. Testing a single
        group here would reject every portal treatment professional the moment
        the portal route is wired through this predicate. Do not "simplify" one
        of these two checks away.

        :param sports.team team: the team the removal targets
        :return bool: True if the current user may remove directly from ``team``
        """
        user = self.env.user
        if user.has_group('base.group_system'):
            return True

        is_treatment_prof = (
            user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
            or user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        )
        if not is_treatment_prof:
            return False

        # Team-scoped: a therapist may only remove from teams where THEY are a
        # (head) therapist, not from any team they can merely see.
        user_staff_roles = team.staff_ids.filtered(
            lambda s: s.user_ids and user.id in s.user_ids.ids
        )
        return any(role.role in REMOVAL_ROLES for role in user_staff_roles)

    def remove_from_team(self, team_id, clear_pending=True, reason=None):
        """
        Public method to remove players from a team with proper permission checks.

        Operates on the whole recordset: ``players.remove_from_team(team.id)``.
        The permission check is per-TEAM, not per-player, so it runs once for the
        call rather than once per record.

        Permissions are defined ONCE in ``_may_remove_from_team`` and shared with
        the portal route:
        - System Administrators (base.group_system) can remove any player.
        - A treatment professional (EITHER TP group) can remove players from
          teams where they are a therapist or head therapist (REMOVAL_ROLES).

        :param int team_id: ID of the team to remove the players from
        :param bool clear_pending: Whether to clear the pending_removal flag (default: True)
        :param str reason: Optional reason for removal (for audit purposes)
        :return: dict: Action result with success notification
        :raises ValidationError: If team is not found or a player is not a member
        :raises AccessError: If user doesn't have permission to remove the players
        """
        team = self.env['sports.team'].browse(team_id)

        # Single permission policy, shared with the portal route (task 1260).
        # The check is per-TEAM, so it runs once for the whole recordset.
        if not self._may_remove_from_team(team):
            raise AccessError(_(
                "You don't have permission to remove players from this team. "
                "Only the team's therapist or head therapist can remove players "
                "directly. Please use the 'Request Removal' action instead."
            ))

        # Now validate team existence and membership
        if not team.exists():
            raise ValidationError(_("Team not found or you don't have access to it"))

        # Membership is per-record, unlike the permission check above.
        for patient in self:
            if team not in patient.team_ids:
                raise ValidationError(_("Player is not a member of the specified team"))

        # Call the private implementation
        return self._remove_from_team(team_id, clear_pending, reason)

    def _remove_from_team(self, team_id, clear_pending=True, reason=None):
        """
        Private method containing the actual sudo operations for team removal.

        CHECK-FREE BY CONTRACT: this method performs NO permission or membership
        validation. Its only caller is the public ``remove_from_team``, which
        runs ``_may_remove_from_team`` and the membership checks first. Do not
        call this directly from a new entry point (the portal route used to, and
        that was exactly the permission gap task 1260 closed) — call the public
        ``remove_from_team`` instead.

        Batched: the roster write is a single write for the whole recordset, so
        recompute_followers and _sync_date_left_last_team each run once instead
        of once per player.

        Chatter is posted once per removal LOT, not once per player: a
        single-record call posts its note on that player's own chatter
        (unchanged); a multi-record call (the wizard's bulk clear) posts ONE
        summary on the TEAM's chatter and nothing on the individual players,
        so the annual "clear all teams" run does not flood every player's
        chatter. Branches on ``len(self)``.

        :param int team_id: ID of the team to remove the players from
        :param bool clear_pending: Whether to clear the pending_removal flag (default: True)
        :param str reason: Optional reason for removal (for audit purposes)
        :return: dict: Action result with success notification
        """
        team = self.env['sports.team'].browse(team_id)
        current_user = self.env.user
        team_name = team.sudo().name
        user_name = current_user.sudo().name

        # Which players actually had the flag: writing pending_removal=False for
        # the whole recordset is a no-op for the rest, but only these get the
        # "flag was cleared" line in their chatter.
        had_pending = (
            self.sudo().filtered('pending_removal') if clear_pending
            else self.browse()
        )

        # Prepare and execute the removal (one write for every player)
        update_vals = {'team_ids': [Command.unlink(team.id)]}
        if had_pending:
            update_vals['pending_removal'] = False
        self.write(update_vals)

        # Chatter branches on recordset size:
        #  - a SINGLE-record call keeps its per-player audit note on the player's
        #    OWN chatter (unchanged) -- 15 call sites, the per-row X, the portal
        #    path and test_player_removal:262 all depend on it;
        #  - a BULK call (the wizard's "clear the team" path) posts NOTHING per
        #    player and ONE summary on the TEAM chatter instead, so the annual
        #    "clear all teams" run does not flood every player's chatter.
        # Dropping the per-player post on the bulk path is genuinely silent:
        # neither `active` nor `team_ids` is tracked on sports.patient (only
        # `pending_removal`), so no tracking entry sneaks back onto a player
        # chatter either.
        is_bulk = len(self) > 1
        success_messages = []
        removed_names = []
        for patient in self:
            # After removing the last team the patient is teamless, so the
            # per-record ir.rule no longer grants the portal user read access to
            # it -> read via sudo() (task 640 follow-up).
            patient_sudo = patient.sudo()

            # Log the action with details
            log_message = _(
                "Player %(player)s removed from team %(team)s by %(user)s"
            ) % {
                'player': patient_sudo.display_name,
                'team': team_name,
                'user': user_name,
            }
            if reason:
                log_message += _("\nReason: %s") % reason
            if patient in had_pending:
                log_message += _("\nPending removal flag was cleared.")

            removed_names.append(patient_sudo.display_name)
            if not patient_sudo.team_ids:
                # Left teamless: _sync_date_left_last_team has stamped the
                # retention clock. The player is NOT archived — that is a manual
                # action now, not a side effect of removal.
                log_message += "\n" + patient_sudo._removal_log_message(team_name, user_name)
                success_message = _('Player successfully removed from team.')
            else:
                # Only set pending_removal if clear_pending is False and not already set
                if not clear_pending and not patient.pending_removal:
                    patient.write({'pending_removal': True})
                    log_message += _("\nPending removal flag was set for the removal request workflow.")
                    success_message = _('Player successfully removed from team. A removal request has been created.')
                else:
                    success_message = _('Player successfully removed from team.')
            success_messages.append(success_message)

            # Per-player chatter -- single-record path only (see note above).
            # Use sudo() to avoid mail system access limitations for portal users
            if not is_bulk:
                patient_sudo.message_post(
                    body=log_message,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )

        if is_bulk:
            # One chatter event per removal lot, on the TEAM. The whole recordset
            # leaves the same team, so this summary is well-defined: who removed
            # them, the date, and the players removed. Nobody is archived by a
            # removal, so the summary makes no claim about archiving.
            removal_date = fields.Date.to_string(fields.Date.context_today(self))
            summary = _(
                "%(count)s players removed from team %(team)s by %(user)s on %(date)s:"
            ) % {
                'count': len(self),
                'team': team_name,
                'user': user_name,
                'date': removal_date,
            }
            summary += "".join("\n- %s" % name for name in removed_names)
            if reason:
                summary += _("\nReason: %s") % reason
            team.sudo().message_post(
                body=summary,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

        # Single-record calls keep their exact original message (15 call sites
        # depend on it); a bulk call gets a summary instead.
        if len(self) == 1:
            message = success_messages[0]
        else:
            message = _(
                "%(count)s players successfully removed from team %(team)s."
            ) % {'count': len(self), 'team': team_name}

        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Player Removed'),
                'message': message,
                'type': 'success',
                'sticky': True,
            }
        }

    @api.model
    def create_portal_patient(self, vals):
        """Public method to create a patient from portal with proper permission checks.
        
        :param dict vals: Values for patient creation including:
            - first_name (required)
            - last_name (required)
            - email (optional)
            - phone (optional)
            - team_ids (optional)
            - date_of_birth (optional)
        :return: Created patient record
        """
        # Validate required fields
        if not vals.get('first_name') or not vals.get('last_name'):
            raise ValidationError(_("First name and last name are required"))
            
        # Check permissions - must be portal treatment professional or team coach
        user = self.env.user
        if not (user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or 
                user.has_group('bemade_sports_clinic.group_portal_team_coach')):
            raise AccessError(_("You don't have permission to create patients"))
        
        # Call the private implementation
        return self._create_portal_patient(vals)
    
    @api.model
    def _create_portal_patient(self, vals):
        """Private method containing the actual @api.model operations for patient creation.
        
        This method is designed to be called from portal controllers where
        portal users need to create patients but might not have direct create
        permissions on res.partner.
        
        :param dict vals: Values for patient creation
        :return: Created patient record
        """
        # Create partner first
        partner_vals = {
            'name': f"{vals['first_name']} {vals['last_name']}",
            'email': vals.get('email', False),
            'phone': vals.get('phone', False),
            'type': 'contact',
        }
        # Optional address fields coming from portal form
        # These are res.partner fields, so capture them here
        for key in ['street', 'street2', 'city', 'zip']:
            if key in vals:
                partner_vals[key] = vals.get(key) or False
        if vals.get('state_id'):
            partner_vals['state_id'] = vals.get('state_id')
        if vals.get('country_id'):
            partner_vals['country_id'] = vals.get('country_id')
        partner = (
            self.env['res.partner']
            .sudo()
            .with_context(tracking_disable=True, mail_create_nosubscribe=True)
            .create(partner_vals)
        )
        
        # Prepare patient values
        patient_vals = {
            'partner_id': partner.id,
            'first_name': vals['first_name'],
            'last_name': vals['last_name'],
        }
        
        # Optional fields
        if 'team_ids' in vals:
            patient_vals['team_ids'] = vals['team_ids']
        if 'date_of_birth' in vals and vals['date_of_birth']:
            patient_vals['date_of_birth'] = vals['date_of_birth']
        # Status fields from portal (treatment professionals only)
        if vals.get('match_status'):
            patient_vals['match_status'] = vals.get('match_status')
        if vals.get('practice_status'):
            patient_vals['practice_status'] = vals.get('practice_status')
        # Other optional patient fields
        if 'allergies' in vals:
            patient_vals['allergies'] = vals.get('allergies') or False
        if 'team_info_notes' in vals:
            patient_vals['team_info_notes'] = vals.get('team_info_notes') or False
        
        # Create patient with tracking disabled to avoid triggering mail/report side-effects
        # Also disable auto-subscriptions on creation
        patient = self.sudo().with_context(
            tracking_disable=True,
            mail_create_nosubscribe=True,
            skip_recompute_followers=True,
        ).create(patient_vals)

        # Optionally recompute followers immediately if explicitly requested by context.
        # Disabled by default for portal flows to avoid mail/report side-effects (e.g., ir.actions.report ACL reads).
        if self.env.context.get('portal_recompute_followers_post_create'):
            patient.sudo().with_context(
                tracking_disable=True,
                mail_create_nosubscribe=True,
            ).recompute_followers()

        return patient

    def recompute_followers(self):
        """Recompute the followers for this patient (and its injuries) based on the
        changes to a specific team's staff members. Ignoring manually unsubscribed
        followers, the set of followers should be the set of staff on all teams the
        patient is part of."""
        for patient in self:
            patient = patient.sudo()
            current_followers = patient.message_partner_ids
            # Read staff with active_test disabled so the eligibility check
            # — not the ORM's active filtering — decides who is dropped. This
            # keeps archived-but-not-unlinked staff (e.g. a contact archived
            # or a user whose portal access was revoked) out of the follower
            # set instead of silently re-subscribing them.
            all_staff = patient.team_ids.with_context(
                active_test=False
            ).mapped("staff_ids")
            future_followers = all_staff.filtered(
                lambda s: s._is_follower_eligible()
            ).mapped("partner_id")
            removed_followers = current_followers - future_followers
            # Only subscribe genuinely-new partners. Subscribing the full
            # ``future_followers`` set on every recompute relies on core's dedup; when
            # the recompute fires more than once in a single flow (e.g. a team is
            # assigned before the patient's first save, so create() and the team-side
            # recompute both run) two inserts can race the mail.followers unique
            # constraint and raise "a partner can't follow an object twice". Computing
            # the net-new set up front keeps recompute_followers idempotent.
            new_followers = future_followers - current_followers

            # Run follower subscribe/unsubscribe operations in a silent mail context
            silent_patient = patient.with_context(
                tracking_disable=True,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_auto_subscribe_no_notify=True,
                mail_notify_force_send=False,
            )
            silent_injuries = patient.injury_ids.with_context(
                tracking_disable=True,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_auto_subscribe_no_notify=True,
                mail_notify_force_send=False,
            )

            # Unsubscribe is driven by the patient's removed set (never per-injury):
            # injuries may carry followers that are not team staff (e.g. assigned
            # treatment professionals), and those must not be stripped here.
            if removed_followers:
                silent_patient.message_unsubscribe(removed_followers.ids)
                silent_injuries.message_unsubscribe(removed_followers.ids)
            if new_followers:
                silent_patient.message_subscribe(new_followers.ids)
            # An individual injury may still be missing team-staff followers even when
            # the patient itself is in sync (e.g. a freshly created injury), so add
            # only the partners each injury is actually missing.
            for injury in silent_injuries:
                injury_new = future_followers - injury.message_partner_ids
                if injury_new:
                    injury.message_subscribe(injury_new.ids)

    # ==================================================================
    # Task 1397 — clinic kiosk: who is this, by name + date of birth
    # ==================================================================
    @staticmethod
    def _kiosk_normalize(text):
        """Fold a name for comparison: strip, casefold, strip accents
        (NFKD + drop combining marks), unify apostrophes, treat hyphens as
        spaces and collapse runs of whitespace. "Émile  Lefèvre-Roy" and
        "emile lefevre roy" compare equal; "Emilie" and "Emile" do not."""
        if not text:
            return ''
        text = unicodedata.normalize('NFKD', str(text))
        text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        text = text.casefold().replace('\u2019', "'").replace('-', ' ')
        return re.sub(r'\s+', ' ', text).strip()

    @api.model
    def _kiosk_match(self, first_name, last_name, date_of_birth, scope):
        """Find THE patient in ``scope`` for what was typed at the kiosk.

        :param scope: the candidate recordset (the clinic's roster — see
            ``sports.event._kiosk_patient_scope``); this method never widens
            it.
        :return: ``(patient, needs_confirmation)`` — an empty recordset when
            there is no unambiguous match (0 or several), so the kiosk can
            only ever answer "not found"; never WHY.

        Rules (owner decisions 2026-08-21):
        * first AND last name must match exactly after normalization;
        * among the name matches, the date of birth decides: exactly one
          candidate with that DOB -> match;
        * no-DOB rule: a UNIQUE name match whose file has no date of birth
          is accepted, flagged ``needs_confirmation`` for the therapist;
        * anything else (DOB mismatch, two homonyms with the same DOB, two
          no-DOB homonyms, name unknown) -> no match.
        """
        first = self._kiosk_normalize(first_name)
        last = self._kiosk_normalize(last_name)
        if not first or not last:
            return self.browse(), False
        candidates = scope.sudo().filtered(
            lambda p: self._kiosk_normalize(p.first_name) == first
            and self._kiosk_normalize(p.last_name) == last)
        if not candidates:
            return self.browse(), False
        if len(candidates) == 1 and not candidates.date_of_birth:
            return candidates, True
        if not date_of_birth:
            return self.browse(), False
        with_dob = candidates.filtered(lambda p: p.date_of_birth == date_of_birth)
        if len(with_dob) == 1:
            return with_dob, False
        return self.browse(), False
