from odoo import models, fields, _, api, Command, SUPERUSER_ID
from odoo.exceptions import ValidationError, AccessError, UserError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.addons.phone_validation.tools import phone_validation
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
    "return_date",
}

internal_tracking_fields = {
    "team_info_notes",
    "age",
    "date_of_birth",
}

# --- Team-dashboard rollup (task 1272) --------------------------------------
# Ranking weight per clinical stage; more concerning stages score higher so the
# most urgent players surface first on the dashboards.
DASHBOARD_STAGE_WEIGHT = {"no_play": 3, "practice_ok": 2, "healthy": 1}
# Default recency window (hours) for "recently active" players; overridable via
# the ir.config_parameter below (none is shipped, so the default applies).
DASHBOARD_WINDOW_HOURS_DEFAULT = 24
DASHBOARD_WINDOW_PARAM = "bemade_sports_clinic.dashboard_activity_window_hours"


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
    _order = "last_name, first_name"
    
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

    def write(self, values):
        res = super().write(values)
        if "team_ids" in values:
            self.sudo().recompute_followers()
            # sudo(), like recompute_followers above: removing a player from
            # their last team makes them teamless, and the per-record ir.rule
            # that granted the acting therapist/portal user access to them was
            # keyed on that team (cf. task 640). The actor loses read access to
            # the very record whose retention clock we still have to settle. This
            # is a system invariant, not a user edit — it must not depend on who
            # happened to trigger the roster change.
            self.sudo()._sync_date_left_last_team()
        if "first_name" in values or "last_name" in values:
            self._recompute_name()
        # Team-dashboard propagation (task 1272). Skip our own rollup writes
        # (dashboard_bump) to avoid recursion.
        if not self.env.context.get("dashboard_bump"):
            self._propagate_patient_dashboard(values)
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

    def _propagate_patient_dashboard(self, values):
        """Bump dashboard rollups for player-level field changes. External
        status (match/practice/return dates) is coach-visible -> both roles;
        internal notes (team_info_notes) are TP-only."""
        changed = set(values)
        if external_tracking_fields & changed:
            self._bump_dashboard_activity({"coach", "tp"})
        elif internal_tracking_fields & changed:
            self._bump_dashboard_activity({"tp"})

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
        self.last_consultation_date = date.today()
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
