from odoo import models, fields, api, _, Command
from odoo.addons.phone_validation.tools import phone_validation
from odoo.exceptions import ValidationError, AccessError
from datetime import timedelta
import logging


_logger = logging.getLogger(__name__)

# Roles allowed to author/edit/dismiss the team announcement (task 1270). All
# other staff (coaches included) get read-only access.
ANNOUNCEMENT_TP_ROLES = ("head_therapist", "therapist", "doctor")


class SportsTeam(models.Model):
    _name = "sports.team"
    _description = "Sports Team"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char()
    event_ids = fields.Many2many(
        comodel_name="sports.event",
        relation="sports_event_team_rel",
        column1="team_id",
        column2="event_id",
        string="Events",
    )
    patient_ids = fields.Many2many(
        comodel_name="sports.patient",
        relation="sports_team_patient_rel",
        column1="team_id",
        column2="patient_id",
        string="Players",
        tracking=True,
    )
    player_count = fields.Integer(compute="_compute_player_counts")
    injured_count = fields.Integer(compute="_compute_player_counts")
    healthy_count = fields.Integer(compute="_compute_player_counts")
    # Three-way team-health breakdown (task 1272) for the red/yellow/green
    # dashboard header. The existing injured_count/healthy_count are only
    # two-way (injured vs not) — insufficient to separate no_play from
    # practice_ok. Reuse the existing sports.patient.stage scheme.
    stage_no_play_count = fields.Integer(
        string="No Play", compute="_compute_stage_counts"
    )
    stage_practice_ok_count = fields.Integer(
        string="Practice OK", compute="_compute_stage_counts"
    )
    stage_healthy_count = fields.Integer(
        string="Healthy", compute="_compute_stage_counts"
    )
    # Backend team-dashboard page (task 1272): players with recent TP-visible
    # activity, ranked by TP dashboard score. Non-stored — recomputed per read
    # so the recency window applies live.
    dashboard_active_patient_ids = fields.Many2many(
        comodel_name="sports.patient",
        string="Recently Active Players",
        compute="_compute_dashboard_active_patients",
    )
    # Portal dashboard (task 1382, digest epic): red/yellow players who are NOT
    # in the recent-changes set, so they stay visible below it. Cheap compute —
    # reuses stage + the existing active set only; no per-player audit query.
    dashboard_watchlist_patient_ids = fields.Many2many(
        comodel_name="sports.patient",
        string="Other Players to Watch",
        compute="_compute_dashboard_watchlist_patients",
    )
    dashboard_upcoming_event_ids = fields.Many2many(
        comodel_name="sports.event",
        string="Upcoming Events",
        compute="_compute_dashboard_upcoming_events",
    )
    # Task 1272 (deferred from #1273): per-team toggle. When on, the player's
    # position is shown as card context on this team's dashboards (portal cards
    # + backend kanban digest). Default off; other teams are unaffected.
    show_position_on_dashboard = fields.Boolean(
        string="Show Player Position on Dashboard",
        default=True,
        help="When enabled, each player's position is shown as context on this "
        "team's dashboard cards.",
    )
    activity_count = fields.Integer(compute="_compute_activity_count")
    # Daily dashboard-digest snapshots (task 1267). One per local date; the
    # capture/purge crons on sports.team.digest maintain them.
    digest_ids = fields.One2many(
        comodel_name="sports.team.digest",
        inverse_name="team_id",
        string="Daily Digests",
    )
    digest_count = fields.Integer(compute="_compute_digest_count")
    digest_retention_days = fields.Integer(
        string="Digest Retention (days)",
        default=365,
        help="How long this team's daily dashboard-digest snapshots are kept "
        "before the purge cron removes them. Set to 0 to keep indefinitely.",
    )
    parent_id = fields.Many2one(
        comodel_name="res.partner",
        string="Parent Organization",
        ondelete="restrict",
        tracking=True,
    )
    staff_ids = fields.One2many(
        comodel_name="sports.team.staff",
        inverse_name="team_id",
        tracking=True,
    )
    head_coach_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_head_coach",
        store=True,
    )
    head_coach_name = fields.Char(
        related="head_coach_id.name",
        string="Head Coach Name",
    )
    head_therapist_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_head_therapist",
        store=True,
        string="Head Therapist",
    )
    head_therapist_name = fields.Char(
        related="head_therapist_id.name",
        string="Head Therapist Name",
    )
    website = fields.Char()
    # Team announcement (task 1270, digest epic slice F). A single TP-authored,
    # all-staff-visible note with an OPTIONAL soft deadline. It stays on the
    # dashboard until a TP dismisses it; the deadline only drives a visual
    # "expired" flag (see _compute_announcement_is_expired). Every change is
    # audited into sports.team.note.history via the write/create hooks. Law 25:
    # broadcast to coaches + emailed, so it must never carry player PHI — the
    # compose surfaces warn the author (backend + portal).
    announcement = fields.Text(
        string="Team Announcement",
        tracking=True,
        help="A note visible to all team staff (coaches included) on the "
        "dashboard and in the morning briefing email. Do NOT include "
        "confidential medical information about any player.",
    )
    announcement_deadline = fields.Date(
        string="Valid Until",
        help="Optional. When set and passed, the announcement is flagged as "
        "expired but stays on the dashboard until a treatment professional "
        "dismisses it.",
    )
    announcement_author_id = fields.Many2one(
        comodel_name="res.users",
        string="Announcement Author",
        readonly=True,
    )
    announcement_date = fields.Datetime(
        string="Announcement Posted On",
        readonly=True,
    )
    announcement_is_expired = fields.Boolean(
        string="Announcement Expired",
        compute="_compute_announcement_is_expired",
        help="True when the announcement has a deadline that has passed. Blank "
        "deadline never expires.",
    )
    note_history_ids = fields.One2many(
        comodel_name="sports.team.note.history",
        inverse_name="team_id",
        string="Announcement History",
        readonly=True,
    )
    allowed_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_allowed_user_ids",
        inverse="_inverse_allowed_user_ids",
    )

    def _roster(self):
        """The full roster, archived members included.

        ``patient_ids`` is read under ``active_test``, which silently drops
        archived players from the very field we need to sync. The Law 25 clock
        sync below MUST go through this — an archived-but-rostered player is an
        allowed state, and a naive read would make _sync_date_left_last_team skip
        the player it was called for. Established idiom in this addon (cf.
        base_partner_merge, patient_merge_wizard).
        """
        return self.sudo().with_context(active_test=False).patient_ids

    def write(self, vals):
        editing_announcement = (
            "announcement" in vals or "announcement_deadline" in vals
        )
        if editing_announcement:
            for rec in self:
                if not rec._user_can_edit_announcement():
                    raise AccessError(
                        _(
                            "Only treatment professionals assigned to this team "
                            "can edit the team announcement."
                        )
                    )
        old_announcements = {}
        if "announcement" in vals:
            vals = dict(vals)
            vals.setdefault("announcement_author_id", self.env.user.id)
            vals.setdefault("announcement_date", fields.Datetime.now())
            old_announcements = {
                rec.id: (rec.announcement or "").strip() for rec in self
            }
        previous_patients = self._roster()
        res = super().write(vals)
        if "staff_ids" in vals or "patient_ids" in vals:
            current_patients = self._roster()
            (current_patients | previous_patients).recompute_followers()
            if "patient_ids" in vals:
                # Maintain the Law 25 retention clock on the team side too. The
                # helper is idempotent and self-correcting, so the union of the
                # previous and current rosters handles joins and leaves in one
                # pass. This is the team-side path that used to leave players
                # teamless with a NULL clock (never anonymized) and let a stale
                # clock survive a rejoin (anonymized early).
                (current_patients | previous_patients)._sync_date_left_last_team()
        if "announcement" in vals:
            self._log_announcement_history(old_announcements)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for index, rec in enumerate(res):
            if "staff_ids" in vals_list[index] or "patient_ids" in vals_list[index]:
                patients = rec._roster()
                patients.recompute_followers()
                if "patient_ids" in vals_list[index]:
                    patients._sync_date_left_last_team()
            if (vals_list[index].get("announcement") or "").strip():
                # Stamp authorship and open the audit trail for a team created
                # with an announcement already set.
                stamp = {}
                if not vals_list[index].get("announcement_author_id"):
                    stamp["announcement_author_id"] = self.env.user.id
                if not vals_list[index].get("announcement_date"):
                    stamp["announcement_date"] = fields.Datetime.now()
                if stamp:
                    super(SportsTeam, rec).write(stamp)
                rec._log_announcement_history({rec.id: ""})
        return res

    # --------------------------------------------------------- announcement (1270)
    @api.onchange("announcement")
    def _onchange_announcement_law25_warning(self):
        """Law 25 (task 1380): the announcement is broadcast to coaches and
        emailed, so it must never carry player PHI. On the backend, surface a
        native warning popup as soon as the author composes/edits content —
        replacing the permanent inline banner. Gated to content present so
        clearing/dismissing the announcement stays silent."""
        if (self.announcement or "").strip():
            return {
                "warning": {
                    "title": _("Privacy (Law 25)"),
                    "message": _(
                        "Visible to all team staff (coaches included) and sent "
                        "by email — do not include any confidential medical "
                        "information about a player."
                    ),
                }
            }

    @api.depends("announcement_deadline")
    def _compute_announcement_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.announcement_is_expired = bool(
                rec.announcement_deadline and rec.announcement_deadline < today
            )

    def _user_can_edit_announcement(self, user=None):
        """Whether ``user`` (default: current) may author/edit/dismiss THIS
        team's announcement. Admins/system always may; otherwise only staff
        holding a treatment-professional role on this team."""
        self.ensure_one()
        user = user or self.env.user
        if user.has_group("base.group_system") or user.has_group(
            "bemade_sports_clinic.group_sports_clinic_admin"
        ):
            return True
        return bool(
            self.sudo().staff_ids.filtered(
                lambda s: s.role in ANNOUNCEMENT_TP_ROLES and user in s.user_ids
            )
        )

    def _log_announcement_history(self, old_by_id):
        """Append one audit row per team whose announcement text changed. The
        action is inferred from the transition: cleared -> ``dismiss``, first
        content -> ``set``, otherwise ``edit``. Created via sudo() so the
        read-only model stays append-only from every role."""
        History = self.env["sports.team.note.history"].sudo()
        for rec in self:
            old = old_by_id.get(rec.id, "")
            new = (rec.announcement or "").strip()
            if new == old:
                continue
            if not new:
                action = "dismiss"
            elif not old:
                action = "set"
            else:
                action = "edit"
            History.create(
                {
                    "team_id": rec.id,
                    "body": rec.announcement or "",
                    "author_id": self.env.user.id,
                    "action": action,
                }
            )

    def action_dismiss_announcement(self):
        """Clear the announcement and log a ``dismiss`` history entry. TP-only
        (enforced by the write guard). 'Stay until dismissed': the deadline is
        only a visual flag, so this is the sole way an announcement leaves the
        dashboard."""
        for rec in self:
            if not rec._user_can_edit_announcement():
                raise AccessError(
                    _(
                        "Only treatment professionals assigned to this team can "
                        "dismiss the team announcement."
                    )
                )
            rec.write({"announcement": False, "announcement_deadline": False})
        return True

    def unlink(self):
        to_recompute = self._roster()
        res = super().unlink()
        to_recompute.recompute_followers()
        # The team is gone; players left teamless by its deletion need their
        # retention clock stamped.
        to_recompute._sync_date_left_last_team()
        return res

    @api.depends("patient_ids.is_injured")
    def _compute_player_counts(self):
        for rec in self:
            rec.player_count = len(rec.patient_ids)
            rec.injured_count = len(rec.patient_ids.filtered(lambda p: p.is_injured))
            rec.healthy_count = rec.player_count - rec.injured_count

    @api.depends("patient_ids.stage")
    def _compute_stage_counts(self):
        for rec in self:
            players = rec.patient_ids
            rec.stage_no_play_count = len(
                players.filtered(lambda p: p.stage == "no_play")
            )
            rec.stage_practice_ok_count = len(
                players.filtered(lambda p: p.stage == "practice_ok")
            )
            rec.stage_healthy_count = len(
                players.filtered(lambda p: p.stage == "healthy")
            )

    @api.depends(
        "patient_ids.dashboard_last_activity_tp", "patient_ids.dashboard_score_tp"
    )
    def _compute_dashboard_active_patients(self):
        cutoff = self.env["sports.patient"]._dashboard_window_cutoff()
        for rec in self:
            active = rec.patient_ids.filtered(
                lambda p: p.dashboard_last_activity_tp
                and p.dashboard_last_activity_tp >= cutoff
            ).sorted(key=lambda p: p.dashboard_score_tp, reverse=True)
            rec.dashboard_active_patient_ids = active

    @api.depends(
        "patient_ids.stage",
        "patient_ids.dashboard_last_activity_tp",
        "patient_ids.dashboard_score_tp",
    )
    def _compute_dashboard_watchlist_patients(self):
        # Red (no_play) + yellow (practice_ok) players who are NOT already in the
        # recent-changes set, ordered red -> yellow then alpha (sort_order splits
        # severity; last_name/first_name break ties). Set difference against the
        # SAME active set the recent-changes list renders from, so no player can
        # appear in both lists.
        for rec in self:
            active = rec.dashboard_active_patient_ids
            watchlist = rec.patient_ids.filtered(
                lambda p: p.stage in ("no_play", "practice_ok") and p not in active
            ).sorted(
                key=lambda p: (p.sort_order, p.last_name or "", p.first_name or "")
            )
            rec.dashboard_watchlist_patient_ids = watchlist

    @api.depends("event_ids.date_start", "event_ids.state")
    def _compute_dashboard_upcoming_events(self):
        now = fields.Datetime.now()
        horizon = now + timedelta(days=7)
        for rec in self:
            events = rec.event_ids.filtered(
                lambda e: e.date_start
                and now <= e.date_start <= horizon
                and e.state != "cancelled"
            ).sorted(key=lambda e: e.date_start)
            rec.dashboard_upcoming_event_ids = events

    @api.depends("staff_ids.role")
    def _compute_head_coach(self):
        for rec in self:
            staff = rec.staff_ids.filtered(lambda r: r.role == "head_coach")
            rec.head_coach_id = staff.partner_id if staff else False

    @api.depends("staff_ids.role")
    def _compute_head_therapist(self):
        for rec in self:
            staff = rec.staff_ids.filtered(lambda r: r.role == "head_therapist")
            rec.head_therapist_id = staff.partner_id if staff else False

    def _compute_activity_count(self):
        for rec in self:
            rec.activity_count = self.env['mail.activity'].search_count([
                ('res_model', '=', 'sports.team'),
                ('res_id', '=', rec.id)
            ])

    def _compute_digest_count(self):
        counts = dict(
            self.env["sports.team.digest"]._read_group(
                [("team_id", "in", self.ids)],
                groupby=["team_id"],
                aggregates=["__count"],
            )
        )
        for rec in self:
            rec.digest_count = counts.get(rec, 0)

    def action_view_digests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Daily Digests"),
            "res_model": "sports.team.digest",
            "view_mode": "list,form",
            "domain": [("team_id", "=", self.id)],
            "context": {"default_team_id": self.id, "create": False},
        }

    def _compute_allowed_user_ids(self):
        for rec in self:
            rec.allowed_user_ids = rec.staff_ids.user_ids

    def _inverse_allowed_user_ids(self):
        for rec in self:
            removed_staff = rec.staff_ids.filtered(
                lambda staff: staff.user_ids not in rec.allowed_user_ids
            )
            added_users = rec.allowed_user_ids - rec.staff_ids.user_ids
            removed_staff.unlink()
            self.env["sports.team.staff"].create(
                [
                    {
                        "team_id": rec.id,
                        "partner_id": user.partner_id.id,
                        "role": "other",
                    }
                    for user in added_users
                ]
            )

    def remove_access(self, user):
        self.staff_ids.filtered(lambda staff: user in staff.user_ids).unlink()


class TeamStaff(models.Model):
    _name = "sports.team.staff"
    _description = "Sports Team Staff"

    sequence = fields.Integer()
    team_id = fields.Many2one(
        comodel_name="sports.team",
        string="Team",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Staff Member",
        required=True,
        domain=[("is_company", "=", False)],
        ondelete="cascade",
    )
    active = fields.Boolean(related="partner_id.active")
    role = fields.Selection(
        selection=[
            ("head_coach", "Head Coach"),
            ("head_therapist", "Head Therapist"),
            ("coach", "Coach"),
            ("therapist", "Therapist"),
            ("doctor", "Doctor"),
            ("other", "Other"),
        ],
        required=True,
    )
    mobile = fields.Char(related="partner_id.phone", readonly=False)
    name = fields.Char(related="partner_id.name", readonly=False)
    parent_id = fields.Many2one(
        related="partner_id.parent_id",
        readonly=False,
        string="Organization",
        domain=[("is_company", "=", True)],
    )
    email = fields.Char(related="partner_id.email", readonly=False)
    user_ids = fields.One2many(related="partner_id.user_ids", readonly=True)
    has_portal_access = fields.Boolean(
        compute="_compute_has_portal_access", compute_sudo=True
    )
    silent_notifications = fields.Boolean(
        string="No Notifications",
        help="When checked, this staff member is granted access but is not "
             "added as a follower of the team's patients/injuries — they "
             "won't receive automatic notifications.",
    )
    is_auto_created = fields.Boolean(
        string="Auto-Created",
        default=False,
        help="True when this staff record was created automatically by an "
             "event-coverage assignment. Auto-created records are removed "
             "when their referencing events end or are cancelled.",
    )
    temporary_event_ids = fields.Many2many(
        comodel_name="sports.event",
        relation="sports_team_staff_event_rel",
        column1="staff_id",
        column2="event_id",
        string="Granting Events",
        help="Events that justify this temporary access. When the last "
             "event is removed and the record is auto-created, the record "
             "is unlinked.",
    )

    _team_staff_unique = models.Constraint(
        'unique(team_id, partner_id)',
        "Each partner can only be related to a given team once.",
    )

    def _is_follower_eligible(self):
        """Whether this staff member should be auto-subscribed as a follower
        of the team's patients/injuries.

        Eligible only while they still hold clinic access:
          - not flagged silent,
          - their contact is active, and
          - if the contact has any user account at all, at least one of those
            users is active. A user whose portal access was revoked (archived)
            must stop receiving notifications even though the contact may
            legitimately stay active; a pure contact that never had a user
            remains a valid follower.
        """
        self.ensure_one()
        if self.silent_notifications:
            return False
        partner = self.partner_id
        if not partner.active:
            return False
        all_users = partner.with_context(active_test=False).user_ids
        if all_users and not all_users.filtered("active"):
            return False
        return True

    @api.constrains("role")
    def _constrain_role(self):
        teams = self.mapped("team_id")
        for team in teams:
            if len(team.staff_ids.filtered(lambda r: r.role == "head_coach")) > 1:
                raise ValidationError(_("A team can have only one head coach."))
            if len(team.staff_ids.filtered(lambda r: r.role == "head_therapist")) > 1:
                raise ValidationError(_("A team can have only one head therapist."))

    @api.onchange("mobile", "partner_id")
    def _onchange_mobile_validation(self):
        if self.mobile:
            self.mobile = self._phone_format(self.mobile, force_format="INTERNATIONAL")

    def _phone_format(self, number, force_format="INTERNATIONAL"):
        country = self.partner_id.country_id or self.env.company.country_id
        if not country or not number:
            return number
        return phone_validation.phone_format(
            number,
            country.code if country else None,
            country.phone_code if country else None,
            force_format=force_format,
            raise_exception=False,
        )

    @api.depends("user_ids", "user_ids.group_ids")
    def _compute_has_portal_access(self):
        for rec in self:
            # Check if the partner has any active users with portal or internal access
            # Use direct group membership check instead of has_group() to avoid security violations
            portal_group = self.env.ref('base.group_portal')
            user_group = self.env.ref('base.group_user')
            rec.has_portal_access = (
                bool(rec.user_ids.filtered(lambda r: portal_group in r.group_ids))
                or bool(rec.user_ids.filtered(lambda r: user_group in r.group_ids))
            )

    def action_revoke_portal_access(self):
        """Public method to revoke portal access with proper permission checks."""
        # Check permissions - only admins and system users can revoke portal access
        if not (self.env.user.has_group('bemade_sports_clinic.group_sports_clinic_admin') or 
                self.env.user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to revoke portal access"))
        
        # Call the private implementation
        return self._action_revoke_portal_access()
    
    def _action_revoke_portal_access(self):
        """Private method containing the actual sudo operations for revoking portal access."""
        group_public = self.env.ref("base.group_public")

        # Archiving the user triggers the staff purge, which DELETES this
        # staff row (dev-review 2026-07-04) — capture the partner first and
        # never touch self afterwards.
        partner = self.partner_id
        # Deactivate the user and set to public user type (standard Odoo approach)
        if self.user_ids:
            self.user_ids.sudo().write(
                {
                    "group_ids": [(6, 0, [group_public.id])],  # Set to public user only
                    "active": False,
                }
            )

        # If there's an active signup invitation, cancel it. Archiving any
        # remaining users is idempotent, so no has_portal_access guard needed
        # (self may already be deleted here).
        if partner:
            Partner = self.env['res.partner'].sudo()
            # signup_valid comes from auth_signup, which may not be installed.
            if 'signup_valid' in Partner._fields:
                Partner.invalidate_model(['signup_valid'])
            users = self.env['res.users'].sudo().search([('partner_id', '=', partner.id)])
            users.write({'active': False})

    def action_grant_portal_access(self):
        wiz = self.env["portal.wizard"].create(
            {"partner_ids": [(4, self.partner_id.id)]}
        )
        return wiz._action_open_modal()

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        
        # Update all portal group memberships for new records
        res._update_all_portal_groups()
        
        # Update group membership based on staff roles
        affected_users = res.mapped('user_ids')
        if affected_users:
            for user in affected_users.sudo():
                res._update_all_portal_groups(user)
        
        # Handle follower recomputation
        res.team_id.mapped("patient_ids").recompute_followers()
        return res

    def unlink(self):
        # Store affected partners and users before deletion
        affected_partners = self.mapped('partner_id')
        affected_users = self.mapped('user_ids')

        # Standard processing for follower recomputation
        patients = self.team_id.mapped("patient_ids")
        res = super().unlink()
        patients.recompute_followers()

        # Drop ex-staff users from any treatment_professional_ids on the
        # affected patients' injuries when they no longer have staff
        # access via any of the patient's other teams. Without this a
        # therapist removed from a team stays assigned to the team's
        # injuries (and as a follower) until manually scrubbed.
        # Same logic for mail.activity records pointing at those
        # injuries — the activity rule won't grant access to the
        # ex-staff user anymore, so leaving the activity assigned to
        # them produces a 403 in the portal next time they open
        # /my/activities. Reassign to a current team therapist or drop.
        if patients:
            patients.injury_ids.sudo()._cleanup_stale_treatment_professionals()
            patients.injury_ids.sudo()._cleanup_stale_mail_activities()

        # After deletion, update group memberships for all affected users
        # Use a new empty recordset to avoid using the deleted recordset
        empty_staff = self.env['sports.team.staff']
        if affected_users:
            for user in affected_users.sudo():
                # Use the comprehensive group update method for each affected user
                empty_staff._update_all_portal_groups(user)

        return res

    def _has_therapist_role(self):
        """Check if the staff member has a therapist role.
        
        Returns:
            bool: True if the staff member has a therapist role, False otherwise.
        """
        return self.role in {'head_therapist', 'therapist'}
    
    def _has_coach_role(self):
        """Check if the staff member has a coach role.
        
        Returns:
            bool: True if the staff member has a coach role, False otherwise.
        """
        return self.role in {'head_coach', 'coach'}
    
    def _get_treatment_professional_group(self):
        """Get the treatment professional security group.
        
        Returns:
            record: The treatment professional security group record.
        """
        return self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
    
    def _get_portal_coach_group(self):
        """Get the portal team coach security group.
        
        Returns:
            record: The portal team coach security group record.
        """
        return self.env.ref('bemade_sports_clinic.group_portal_team_coach')
    
    def _update_user_group_membership(self, user, should_have_access, treatment_prof_group):
        """Update group membership for a single user.
        
        Args:
            user (res.users): The user to update
            should_have_access (bool): Whether the user should have treatment professional access
            treatment_prof_group (res.groups): The treatment professional group
        """
        # Use direct group membership check instead of has_group() to avoid security violations
        has_access = treatment_prof_group in user.group_ids
        
        if should_have_access and not has_access:
            user.sudo().write({'group_ids': [(4, treatment_prof_group.id)]})
        elif not should_have_access and has_access:
            user.sudo().write({'group_ids': [(3, treatment_prof_group.id)]})
    
    def _get_staff_with_therapist_roles(self, partner_id):
        """Get all staff records with therapist roles for a partner.
        
        Args:
            partner_id (int): ID of the partner to check
            
        Returns:
            recordset: Staff records with therapist roles
        """
        return self.env['sports.team.staff'].sudo().search([
            ('partner_id', '=', partner_id),
            ('role', 'in', ['head_therapist', 'therapist', 'doctor'])
        ])
    
    def _get_staff_with_coach_roles(self, partner_id):
        """Get all staff records with coach roles for a partner.
        
        Args:
            partner_id (int): ID of the partner to check
            
        Returns:
            recordset: Staff records with coach roles
        """
        return self.env['sports.team.staff'].sudo().search([
            ('partner_id', '=', partner_id),
            ('role', 'in', ['head_coach', 'coach'])
        ])
    
    def update_all_treatment_professional_groups(self):
        """Manual method to update treatment professional group assignments for all staff.
        
        This can be called to refresh group assignments after role changes or system updates.
        Useful for fixing cases where staff members were added but not assigned to correct groups.
        
        Updated to use comprehensive group assignment that handles both therapist and coach roles.
        """
        all_staff = self.env['sports.team.staff'].search([])
        all_staff._update_all_portal_groups()
        return True
    
    def update_all_portal_groups(self):
        """Manual method to update all portal group assignments for all staff.
        
        This can be called to refresh group assignments after role changes or system updates.
        Useful for fixing cases where staff members were added but not assigned to correct groups.
        """
        all_staff = self.env['sports.team.staff'].search([])
        all_staff._update_all_portal_groups()
        return True
    
    def _update_all_portal_groups(self, specific_user=None):
        """Update all portal group assignments based on staff roles.
        
        This method ensures that users have the appropriate portal group memberships
        based on their roles. It handles both therapist and coach roles.
        
        Args:
            specific_user (res.users, optional): If provided, only update this specific user.
                                                Otherwise, update all users for the staff records.
        """
        # Skip if in module installation context to avoid demo data conflicts
        if self.env.context.get('module'):
            return
            
        treatment_prof_group = self._get_treatment_professional_group()
        portal_treatment_prof_group = self.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        portal_coach_group = self._get_portal_coach_group()
        portal_group = self.env.ref('base.group_portal')
        user_group = self.env.ref('base.group_user')
        
        if specific_user:
            # Process only the specific user
            has_therapist_role = bool(self._get_staff_with_therapist_roles(specific_user.partner_id.id))
            has_coach_role = bool(self._get_staff_with_coach_roles(specific_user.partner_id.id))

            # Log basic diagnostic info without relying on xml_id (not a real field)
            _logger.debug(
                "[SportsTeam] _update_all_portal_groups specific_user=%s partner_id=%s has_therapist_role=%s has_coach_role=%s group_ids=%s",
                specific_user.id,
                specific_user.partner_id.id,
                has_therapist_role,
                has_coach_role,
                specific_user.group_ids.ids,
            )
            
            # Handle internal users
            if user_group in specific_user.group_ids:
                # Internal users get treatment professional group for therapist roles
                if has_therapist_role and treatment_prof_group not in specific_user.group_ids:
                    specific_user.sudo().write({'group_ids': [(4, treatment_prof_group.id)]})
                    _logger.debug("[SportsTeam] Added internal treatment group to user %s", specific_user.id)
                elif not has_therapist_role and treatment_prof_group in specific_user.group_ids:
                    specific_user.sudo().write({'group_ids': [(3, treatment_prof_group.id)]})
                    _logger.debug("[SportsTeam] Removed internal treatment group from user %s", specific_user.id)
            # Handle portal users
            elif portal_group in specific_user.group_ids:
                # Portal users get appropriate portal groups
                if has_therapist_role and portal_treatment_prof_group not in specific_user.group_ids:
                    specific_user.sudo().write({'group_ids': [(4, portal_treatment_prof_group.id)]})
                    _logger.debug("[SportsTeam] Added portal treatment group to user %s", specific_user.id)
                elif not has_therapist_role and portal_treatment_prof_group in specific_user.group_ids:
                    specific_user.sudo().write({'group_ids': [(3, portal_treatment_prof_group.id)]})
                    _logger.debug("[SportsTeam] Removed portal treatment group from user %s", specific_user.id)

                if has_coach_role and portal_coach_group not in specific_user.group_ids:
                    specific_user.sudo().write({'group_ids': [(4, portal_coach_group.id)]})
                    _logger.debug("[SportsTeam] Added portal coach group to user %s", specific_user.id)
                elif not has_coach_role and portal_coach_group in specific_user.group_ids:
                    specific_user.sudo().write({'group_ids': [(3, portal_coach_group.id)]})
                    _logger.debug("[SportsTeam] Removed portal coach group from user %s", specific_user.id)
            return
        
        # Process staff members with users if no specific user provided
        for staff in self.filtered('user_ids'):
            has_therapist_role = bool(self._get_staff_with_therapist_roles(staff.partner_id.id))
            has_coach_role = bool(self._get_staff_with_coach_roles(staff.partner_id.id))
            
            for user in staff.user_ids:
                # Handle internal users
                if user_group in user.group_ids:
                    # Internal users get treatment professional group for therapist roles
                    if has_therapist_role and treatment_prof_group not in user.group_ids:
                        user.sudo().write({'group_ids': [(4, treatment_prof_group.id)]})
                    elif not has_therapist_role and treatment_prof_group in user.group_ids:
                        user.sudo().write({'group_ids': [(3, treatment_prof_group.id)]})
                # Handle portal users
                elif portal_group in user.group_ids:
                    # Portal users get appropriate portal groups
                    if has_therapist_role and portal_treatment_prof_group not in user.group_ids:
                        user.sudo().write({'group_ids': [(4, portal_treatment_prof_group.id)]})
                    elif not has_therapist_role and portal_treatment_prof_group in user.group_ids:
                        user.sudo().write({'group_ids': [(3, portal_treatment_prof_group.id)]})
                        
                    if has_coach_role and portal_coach_group not in user.group_ids:
                        user.sudo().write({'group_ids': [(4, portal_coach_group.id)]})
                    elif not has_coach_role and portal_coach_group in user.group_ids:
                        user.sudo().write({'group_ids': [(3, portal_coach_group.id)]})
    
    def _update_treatment_professional_group(self, specific_user=None):
        """Update treatment professional status based on staff role.
        
        This method ensures that users with therapist roles have the appropriate
        group memberships. It handles both internal and portal users appropriately.
        
        For internal users, this manages group membership directly.
        For portal users, it manages the portal treatment professional group.
        
        Args:
            specific_user (res.users, optional): If provided, only update this specific user.
                                                Otherwise, update all users for the staff records.
        """
        # Skip if in module installation context to avoid demo data conflicts
        if self.env.context.get('module'):
            return
            
        treatment_prof_group = self._get_treatment_professional_group()
        portal_treatment_prof_group = self.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        
        if specific_user:
            # Process only the specific user
            staff = self.filtered(lambda s: specific_user in s.user_ids)
            if not staff:
                # Check if the user has any therapist roles through their partner
                has_therapist_role = bool(self._get_staff_with_therapist_roles(specific_user.partner_id.id))
                users_to_process = specific_user
            else:
                # Check if this partner has any staff records with therapist roles
                has_therapist_role = bool(self._get_staff_with_therapist_roles(specific_user.partner_id.id))
                users_to_process = specific_user
            
            # Apply the appropriate group membership
            # Use direct group membership check instead of has_group() to avoid security violations
            portal_group = self.env.ref('base.group_portal')
            if portal_group not in users_to_process.group_ids:
                # Internal user
                if has_therapist_role and treatment_prof_group not in users_to_process.group_ids:
                    users_to_process.sudo().write({'group_ids': [(4, treatment_prof_group.id)]})
                elif not has_therapist_role and treatment_prof_group in users_to_process.group_ids:
                    users_to_process.sudo().write({'group_ids': [(3, treatment_prof_group.id)]})
            else:
                # Portal user
                if has_therapist_role and portal_treatment_prof_group not in users_to_process.group_ids:
                    users_to_process.sudo().write({'group_ids': [(4, portal_treatment_prof_group.id)]})
                elif not has_therapist_role and portal_treatment_prof_group in users_to_process.group_ids:
                    users_to_process.sudo().write({'group_ids': [(3, portal_treatment_prof_group.id)]})
            return
        
        # Process staff members with users if no specific user provided
        for staff in self.filtered('user_ids'):
            # Check if this partner has any staff records with therapist roles
            has_therapist_role = bool(self._get_staff_with_therapist_roles(staff.partner_id.id))
            
            # Process each user linked to this partner
            portal_group = self.env.ref('base.group_portal')
            user_group = self.env.ref('base.group_user')
            for user in staff.user_ids:
                # Handle internal users
                if user_group in user.group_ids:
                    self._update_user_group_membership(user, has_therapist_role, treatment_prof_group)
                # Handle portal users
                elif portal_group in user.group_ids:
                    if has_therapist_role and portal_treatment_prof_group not in user.group_ids:
                        user.sudo().write({'group_ids': [(4, portal_treatment_prof_group.id)]})
                    elif not has_therapist_role and portal_treatment_prof_group in user.group_ids:
                        user.sudo().write({'group_ids': [(3, portal_treatment_prof_group.id)]})
    
    def write(self, vals):
        previous_patients = self.team_id.patient_ids if 'team_id' in vals else self.env['sports.patient']
        result = super().write(vals)

        if 'role' in vals or 'team_id' in vals:
            self._update_all_portal_groups()

        if 'team_id' in vals or 'silent_notifications' in vals or 'role' in vals:
            affected_patients = self.team_id.patient_ids | previous_patients
            affected_patients.recompute_followers()
            # If team_id moved a staff member to a different team, the
            # patients on the *previous* team may have stale TP injury
            # assignments to clean up. (silent_notifications and role
            # changes don't affect access to the patient itself.)
            if 'team_id' in vals and previous_patients:
                previous_patients.injury_ids.sudo()._cleanup_stale_treatment_professionals()
                previous_patients.injury_ids.sudo()._cleanup_stale_mail_activities()

        return result
