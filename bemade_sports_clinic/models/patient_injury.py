from odoo import models, fields, api, _
from datetime import datetime, date
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


def legacy_change_emails_enabled(env):
    """Task 1269: master switch for the three legacy per-change follower emails
    (play-status update, injury field-edit, internal-note). Default OFF — those
    per-change pushes are replaced by the 5-min aggregated urgent-notification
    cron plus the dashboard/daily-digest surfaces. Kept behind a config flag so
    the old behaviour can be restored without a code change."""
    raw = env['ir.config_parameter'].sudo().get_param(
        'bemade_sports_clinic.legacy_change_emails_enabled')
    if raw is None or raw is False:
        return False
    return str(raw).strip().lower() not in ('', '0', 'false', 'none')


external_tracking_fields = {
    "diagnosis",
    "predicted_resolution_date",
    "resolution_date",
    "external_notes",
}

# Include only fields not already included in external_tracking_fields here
internal_tracking_fields = {
    "internal_notes",
    "parental_consent",
}

# Task 1241: note fields snapshotted to the append-only
# sports.injury.note.history audit model on every real change.
note_history_scope_by_field = {
    "internal_notes": "internal",
    "external_notes": "external",
}

# --- Team-dashboard propagation (task 1272) ---------------------------------
# Injury field changes that are clinically/externally visible -> bump BOTH the
# coach and TP rollups (unless the injury is hidden from coaches). Note fields
# (internal_notes/external_notes) are deliberately NOT here: they are handled
# once, at the source, by the sports.injury.note.history create hook, so they
# are never double-counted.
dashboard_external_injury_fields = {
    "diagnosis",
    "stage",
    "severity",
    "predicted_resolution_date",
    "resolution_date",
    "body_location",
    "injury_type",
}
# Internal/administrative changes -> TP rollup only.
# Task 1381: treatment_professional_ids untracked from the dashboard changelog
# (still tracking=True on the field, so chatter still records it). Forward-only:
# historical digest snapshots keep any previously frozen TP change lines.
dashboard_internal_injury_fields = {
    "parental_consent",
}


class PatientInjury(models.Model):
    _name = "sports.patient.injury"
    _description = "Patient Injury"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "diagnosis"
    _order = "create_date desc, id desc"

    @api.model
    def _today(self):
        """Get the current date in the user's time zone."""
        return datetime.now(self.env.tz)

    # TODO: Find a way to improve notifications sent about tracking injury details

    patient_id = fields.Many2one(
        comodel_name="sports.patient",
        string="Patient",
        readonly=True,
        required=True,
        ondelete="cascade",
    )
    patient_name = fields.Char(related="patient_id.name")
    team_id = fields.Many2one(
        comodel_name="sports.team",
        string="Team",
        # The picker is scoped to the patient's teams via the
        # `allowed_team_ids` helper field below — OWL's domain
        # evaluator can't safely short-circuit chained access
        # through a possibly-empty patient_id m2o, so we expose
        # the resolved id list as its own field on the record.
        domain="[('id', 'in', allowed_team_ids)]",
        help="The team for which this injury was reported, especially important when a player belongs to multiple teams.",
    )
    allowed_team_ids = fields.Many2many(
        comodel_name='sports.team',
        relation='sports_patient_injury_allowed_team_rel',
        column1='injury_id',
        column2='team_id',
        compute='_compute_allowed_team_ids',
        store=False,
        compute_sudo=True,
        help="Teams the patient belongs to — used to scope the team_id picker.",
    )
    diagnosis = fields.Char(tracking=True)

    injury_date = fields.Date(
        string="Date of Injury",
        default=_today,
    )
    injury_date_na = fields.Boolean(string="N/A", default=False)
    internal_notes = fields.Text(tracking=True)
    external_notes = fields.Text(tracking=True)
    treatment_professional_ids = fields.Many2many(
        comodel_name="res.users",
        relation="patient_injury_treatment_pro_rel",
        column1="patient_injury_id",
        column2="treatment_pro_id",
        string="Treatment Professionals",

        tracking=True,
    )
    predicted_resolution_date = fields.Date(tracking=True)
    resolution_date = fields.Date(
        tracking=True, help="The date when the injury was actually resolved."
    )
    stage = fields.Selection(
        selection=[
            ("unverified", "Unverified"),
            ("active", "Active"),
            ("resolved", "Resolved")
        ],
        string="Status",
        default="unverified",
        tracking=True,
        copy=False,
        help="""
        - Unverified: Injury has been reported but not yet verified by a treatment professional
        - Active: Injury has been verified and is being treated
        - Resolved: Injury has been resolved
        """
    )
    hidden_from_coaches = fields.Boolean(
        string="Hidden from Coaches",
        default=False,
        tracking=True,
        help="When checked, team coaches cannot see this injury in the portal "
             "or anywhere else. Treatment professionals and clinic admins "
             "still see it normally.",
    )
    parental_consent = fields.Selection(
        string="Consent for Disclosure to Parent",
        selection=[("yes", "Yes"), ("no", "No"), ("na", "Not Applicable")],
        help="Whether the patient has given their consent to share injury details with their parents.",
        tracking=True,
    )
    
    # Fields for injury categorization - using Char instead of foreign keys
    # NOTE: These fields are currently retained for potential future use.
    # They provide structured injury categorization that may be valuable for
    # reporting, analytics, or enhanced injury tracking features.
    body_location = fields.Char(
        string="Body Location",
        help="The anatomical location of the injury (retained for future use)",
        tracking=True,
    )
    
    injury_type = fields.Char(
        string="Injury Type",
        help="The type of injury (e.g., sprain, fracture, strain) - retained for future use",
        tracking=True,
    )
    
    severity = fields.Selection(
        selection=[
            ("mild", "Mild"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
        ],
        string="Severity",
        help="The assessed severity of the injury (retained for future use)",
        tracking=True,
    )
    
    # Relations to new models
    # Now treatment notes are linked to patient primarily, but can be optionally linked to injuries
    treatment_note_ids = fields.One2many(
        comodel_name='sports.treatment.note',
        inverse_name='injury_id',
        string='Treatment Notes',
        help='Treatment notes specifically linked to this injury'
    )
    treatment_note_count = fields.Integer(
        string='Treatment Note Count',
        compute='_compute_treatment_note_count'
    )
    document_ids = fields.One2many(
        comodel_name='sports.injury.document',
        inverse_name='injury_id',
        string='Documents'
    )
    document_count = fields.Integer(
        string='Document Count',
        compute='_compute_document_count'
    )
    activity_count = fields.Integer(
        string='Activity Count',
        compute='_compute_activity_count'
    )
    note_history_ids = fields.One2many(
        comodel_name='sports.injury.note.history',
        inverse_name='injury_id',
        string='Note History',
        readonly=True,
        help='Append-only audit trail of internal/external note changes.',
    )

    @api.depends('patient_id', 'patient_id.team_ids')
    def _compute_allowed_team_ids(self):
        for record in self:
            record.allowed_team_ids = record.patient_id.team_ids if record.patient_id else False

    @api.depends('treatment_note_ids')
    def _compute_treatment_note_count(self):
        for record in self:
            record.treatment_note_count = len(record.treatment_note_ids)
            
    @api.depends('document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)
    
    def _compute_activity_count(self):
        for rec in self:
            rec.activity_count = self.env['mail.activity'].search_count([
                ('res_model', '=', 'sports.patient.injury'),
                ('res_id', '=', rec.id)
            ])
    
    @api.constrains("injury_date_na", "injury_date")
    def constrain_date_blank_only_if_na(self):
        for rec in self:
            if not rec.injury_date_na and not rec.injury_date:
                raise ValidationError(
                    _("If injury date is not set, the N/A box must be checked.")
                )

    @api.onchange("injury_date_na")
    def _onchange_injury_date_na(self):
        for rec in self:
            if rec.injury_date_na:
                rec.injury_date = None

    @api.onchange("injury_date")
    def _onchange_injury_date(self):
        for rec in self:
            if rec.injury_date:
                rec.injury_date_na = False

    def action_verify_injury(self):
        """Verify an injury, changing its status from unverified to active.
        Only treatment professionals or internal users with appropriate rights can verify injuries."""
        self.ensure_one()
        if self.stage != "unverified":
            raise UserError(_("Only unverified injuries can be verified."))
        
        # Check if current user is a treatment professional or has appropriate rights.
        # Portal treatment professionals must be allowed too: the portal injury
        # verify route/button is exposed to them and gates team access separately
        # (controllers.verify_injury -> _check_access_to_injury).
        if not (self.env.user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional') or
                self.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or
                self.env.user.has_group('base.group_system')):
            raise AccessError(_("Only treatment professionals can verify injuries."))
            
        self.write({'stage': 'active'})
        message = _("Injury verified by %s") % self.env.user.name
        self.message_post(body=message)
        # Close any open verification activities for this injury
        model_rec = self.env['ir.model']._get('sports.patient.injury')
        verif_acts = self.env['mail.activity'].sudo().search([
            ('res_model_id', '=', model_rec.id),
            ('res_id', '=', self.id),
            ('summary', '=', 'Verify injury'),
            ('active', '=', True),
        ])
        if verif_acts:
            verif_acts.action_done()
        return True
        
    def action_resolve_injury(self):
        """Mark an injury as resolved."""
        self.ensure_one()
        if self.stage == "resolved":
            return True
            
        self.write({
            'stage': 'resolved',
            'resolution_date': fields.Date.context_today(self)
        })
        message = _("Injury marked as resolved by %s") % self.env.user.name
        self.message_post(body=message)
        return True

    # Task 1269 dead-code cleanup: a first ``create`` was defined here and
    # immediately shadowed by the fuller ``@api.model_create_multi`` override
    # below (Python keeps the last definition), so it never executed. Its
    # side-effects are already covered by the active override — treatment-
    # professional subscriptions via ``_manage_treatment_professional_subscriptions``
    # and injury follower propagation via ``patient_id.recompute_followers()``
    # (which subscribes the team-staff follower set onto each injury). The only
    # unique behaviour was a chatter post carrying the injury *diagnosis* onto
    # the patient thread — dead code, and PHI we deliberately do NOT resurrect.
    # The shadow is removed here so the single active ``create`` is the only one.

    def _note_history_author_id(self):
        """Resolve the authenticated author for note-history rows (task 1241).

        Portal saves go through ``injury.sudo().write(vals)``, which rebinds
        the environment to the superuser; the audit trail must credit the
        human behind the request, so when running as sudo inside an HTTP
        request we recover the session uid instead.
        """
        if self.env.su and request and request.session and request.session.uid:
            return request.session.uid
        return self.env.uid

    def _prepare_note_history_vals(self, vals):
        """Build sports.injury.note.history vals for note fields that actually
        change in ``vals``, comparing old vs new per record. A save that
        doesn't change the field produces no row (task 1241).

        Task 1404: comparison is strip-normalized so whitespace-only diffs
        log nothing, and an essentially-empty NEW value — including a genuine
        clear — logs nothing (customer decision; the traceability trade-off on
        clear events is explicitly accepted). Stored content stays raw
        (un-stripped); normalization is for comparison only. The invariant is
        that no history row ever has essentially-empty content."""
        changed_fields = [f for f in note_history_scope_by_field if f in vals]
        if not changed_fields:
            return []
        history_vals = []
        author_id = self._note_history_author_id()
        now = fields.Datetime.now()
        for rec in self:
            for fname in changed_fields:
                old_norm = (rec[fname] or "").strip()
                new_norm = (vals.get(fname) or "").strip()
                if old_norm == new_norm:
                    continue
                if not new_norm:
                    # Clears and whitespace-only writes log nothing.
                    continue
                history_vals.append({
                    'injury_id': rec.id,
                    'scope': note_history_scope_by_field[fname],
                    'content': vals.get(fname),
                    'author_id': author_id,
                    'note_datetime': now,
                })
        return history_vals

    def write(self, vals):
        """Override write to update subscriptions if treatment professionals change"""
        # Store current treatment professional IDs before update
        old_treatment_prof_ids = {}
        if 'treatment_professional_ids' in vals:
            for rec in self:
                old_treatment_prof_ids[rec.id] = rec.treatment_professional_ids.ids

        # Detect suppression context (portal coach flows)
        suppress_followers = bool(
            self.env.context.get('mail_create_nosubscribe')
            or self.env.context.get('mail_notrack')
            or self.env.context.get('suppress_portal_mail')
        )

        # Task 1241: snapshot note changes into the append-only history.
        # Deliberately NOT gated on suppress_followers — the audit capture
        # must happen even under mail_notrack/suppress contexts; only the
        # explicit skip_note_history context disables it.
        note_history_vals = []
        if not self.env.context.get('skip_note_history'):
            note_history_vals = self._prepare_note_history_vals(vals)

        res = super().write(vals)

        if note_history_vals:
            # sudo: history rows are only ever created by server code; no
            # group holds create rights on the model.
            self.env['sports.injury.note.history'].sudo().create(note_history_vals)
        
        # If treatment professionals changed, update subscriptions (unless suppressed)
        if not suppress_followers and 'treatment_professional_ids' in vals:
            for rec in self:
                # Only run subscription manager if treatment professionals actually changed
                if rec.id in old_treatment_prof_ids and set(old_treatment_prof_ids[rec.id]) != set(rec.treatment_professional_ids.ids):
                    rec._manage_treatment_professional_subscriptions()
                    
                    # Log the change in treatment professionals
                    new_profs = rec.treatment_professional_ids - self.env['res.users'].browse(old_treatment_prof_ids[rec.id])
                    removed_profs = self.env['res.users'].browse(old_treatment_prof_ids[rec.id]) - rec.treatment_professional_ids
                    
                    # Create user-friendly message
                    msg = ''
                    if new_profs:
                        prof_names = ', '.join(new_profs.mapped('name'))
                        msg += _('Added treatment professional(s): %s. ') % prof_names
                    if removed_profs:
                        prof_names = ', '.join(removed_profs.mapped('name'))
                        msg += _('Removed treatment professional(s): %s.') % prof_names
                    
                    if msg:
                        rec.message_post(body=msg)
                        
        # Also update subscriptions if internal_notes changes (unless suppressed)
        if not suppress_followers and 'internal_notes' in vals:
            for rec in self:
                rec._manage_treatment_professional_subscriptions()

        # Task 1272: propagate non-note injury changes to the owning player's
        # dashboard rollups. Note changes are handled by the note-history hook.
        if not self.env.context.get('dashboard_bump'):
            for rec in self:
                rec._propagate_injury_dashboard(vals)

        return res

    def _propagate_injury_dashboard(self, vals):
        """Bump the owning player's dashboard rollups for this injury change
        (task 1272). Law 25: a hidden injury only ever touches the TP rollup;
        toggling visibility bumps the coach rollup only when the injury BECOMES
        visible again."""
        self.ensure_one()
        patient = self.patient_id
        if not patient:
            return
        changed = set(vals)
        roles = set()
        if 'hidden_from_coaches' in changed:
            # Becoming visible again is coach-relevant; becoming hidden is not.
            roles |= {'tp'} if self.hidden_from_coaches else {'coach', 'tp'}
        if self.hidden_from_coaches:
            if changed & (dashboard_external_injury_fields
                          | dashboard_internal_injury_fields):
                roles |= {'tp'}
        else:
            if changed & dashboard_external_injury_fields:
                roles |= {'coach', 'tp'}
            if changed & dashboard_internal_injury_fields:
                roles |= {'tp'}
        if roles:
            patient._bump_dashboard_activity(roles)
        
    def _cleanup_stale_treatment_professionals(self):
        """For each injury in self, drop from treatment_professional_ids
        any user who no longer has staff access to the patient (i.e. is
        not on staff of any team the patient belongs to). Used by the
        team-staff unlink/write hooks to keep injury TP assignments in
        sync with the team-staff source of truth."""
        for injury in self:
            if not injury.treatment_professional_ids:
                continue
            patient = injury.patient_id
            accessible_user_ids = set(patient.team_ids.mapped('staff_ids.user_ids').ids)
            stale = injury.treatment_professional_ids.filtered(
                lambda u: u.id not in accessible_user_ids
            )
            if stale:
                injury.with_context(
                    mail_notrack=True,
                    mail_create_nolog=True,
                    mail_create_nosubscribe=True,
                ).write({
                    'treatment_professional_ids': [(3, u.id) for u in stale],
                })

    def _cleanup_stale_mail_activities(self):
        """Reassign or close mail.activity records on injuries in self that
        are still assigned to users who no longer have staff access to the
        patient. Without this, tightening the portal mail.activity rule
        would silently hide stale assignee activities — leaving them
        invisible to the original assignee while still cluttering the
        backend.

        Strategy: prefer reassigning to a current head therapist on the
        patient's teams (then any therapist), so the work follows the
        team. If no replacement is available, drop the activity
        entirely — the verification cron will re-create what it needs.
        """
        Activity = self.env['mail.activity'].sudo()
        model_rec = self.env['ir.model']._get('sports.patient.injury')
        for injury in self.sudo():
            patient = injury.patient_id
            if not patient:
                continue
            current_user_ids = set(patient.team_ids.mapped('staff_ids.user_ids').ids)
            activities = Activity.search([
                ('res_model_id', '=', model_rec.id),
                ('res_id', '=', injury.id),
            ])
            stale = activities.filtered(
                lambda a: a.user_id and a.user_id.id not in current_user_ids
            )
            if not stale:
                continue
            # Pick replacement assignee from the patient's current teams.
            therapist_staff = patient.team_ids.mapped('staff_ids').filtered(
                lambda s: s.role in ('head_therapist', 'therapist')
            )
            head = therapist_staff.filtered(lambda s: s.role == 'head_therapist')
            replacement_user = (
                (head.mapped('user_ids')[:1])
                or (therapist_staff.mapped('user_ids')[:1])
            )
            if replacement_user:
                stale.write({'user_id': replacement_user.id})
            else:
                stale.unlink()

    def _manage_treatment_professional_subscriptions(self):
        """Subscribe treatment professionals to both regular and internal note updates
        while ensuring non-treatment professionals only subscribe to external updates."""
        # Skip entirely when portal flows suppress mail operations to avoid mail.followers access
        if (
            self.env.context.get('mail_create_nosubscribe')
            or self.env.context.get('mail_notrack')
            or self.env.context.get('suppress_portal_mail')
        ):
            return
        self.ensure_one()
        
        # Get the message subtypes
        external_subtype = self.env.ref('bemade_sports_clinic.subtype_patient_injury_external_update')
        internal_subtype = self.env.ref('bemade_sports_clinic.subtype_patient_injury_internal_update')
        
        # Get all followers
        followers = self.env['mail.followers'].search([
            ('res_model', '=', 'sports.patient.injury'),
            ('res_id', '=', self.id)
        ])

        # Apply silent context to follower updates to avoid notification spam
        silent_followers = followers.with_context(
            tracking_disable=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
            mail_auto_subscribe_no_notify=True,
            mail_notify_force_send=False,
        )

        for follower in silent_followers:
            partner = self.env['res.partner'].browse(follower.partner_id.id)
            users = self.env['res.users'].search([('partner_id', '=', partner.id)])
            
            # Check if any of the users is a treatment professional
            # Note: We can't use has_group() on non-current users, so we check group membership directly
            is_treatment_prof = False
            treatment_prof_group = self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
            for user in users:
                if treatment_prof_group in user.group_ids:
                    is_treatment_prof = True
                    break
            
            # Update follower subtypes based on role
            if is_treatment_prof:
                # Treatment professionals get both types of notifications
                follower.write({
                    'subtype_ids': [(6, 0, [external_subtype.id, internal_subtype.id])]
                })
            else:
                # Regular users only get external notifications
                follower.write({
                    'subtype_ids': [(6, 0, [external_subtype.id])]
                })
                
        # Make sure treatment professionals (if any) are subscribed
        if self.treatment_professional_ids:
            self.with_context(
                tracking_disable=True,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_auto_subscribe_no_notify=True,
                mail_notify_force_send=False,
            ).message_subscribe(
                partner_ids=self.treatment_professional_ids.mapped('partner_id').ids,
                subtype_ids=[external_subtype.id, internal_subtype.id]
            )

    def unlink(self):
        # Capture (patient, roles) before deletion so the dashboard rollups can
        # be refreshed afterwards from the remaining injuries (task 1272).
        to_bump = []
        for rec in self:
            msg_body = _("An injury was deleted.")
            if rec.diagnosis:
                msg_body += _(" Diagnosis: %s." % rec.diagnosis)
            rec.patient_id.message_post(body=msg_body, message_type="comment")
            if rec.patient_id:
                roles = ('tp',) if rec.hidden_from_coaches else ('coach', 'tp')
                to_bump.append((rec.patient_id, set(roles)))
        res = super().unlink()
        if not self.env.context.get('dashboard_bump'):
            for patient, roles in to_bump:
                patient._bump_dashboard_activity(roles)
        return res

    def action_view_injury_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "sports.patient.injury",
            "res_id": self.id,
            "context": self.env.context,
        }

    def action_view_patient(self):
        """Smart-button back-link from the injury form to its player."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "sports.patient",
            "res_id": self.patient_id.id,
            "context": self.env.context,
        }

    def _track_subtype(self, init_values):
        return self.env.ref("mail.mt_note")

    def _track_template(self, changes):
        res = super()._track_template(changes)
        # Task 1269: the injury field-edit and internal-note per-change emails are
        # replaced by the aggregated urgent-notification cron + dashboard/digest.
        # Keep the tracking/chatter audit log (super() already recorded it) but
        # only attach the notifying templates when the legacy flag is on.
        if not legacy_change_emails_enabled(self.env):
            return res
        params = set(changes)
        external = bool(external_tracking_fields & params)
        if external:
            first_external_field = (external_tracking_fields & params).pop()
            res[first_external_field] = (
                self.env.ref(
                    "bemade_sports_clinic.mail_template_patient_injury_status_update"
                ),
                {
                    "auto_delete": False,
                    "subtype_id": self.env.ref(
                        "bemade_sports_clinic.subtype_patient_injury_external_update"
                    ).id,
                    "email_layout_xmlid": "mail.mail_notification_light",
                },
            )
        if "internal_notes" in changes:
            res["internal_notes"] = (
                self.env.ref(
                    "bemade_sports_clinic.mail_template_patient_injury_new_internal_note"
                ),
                {
                    "auto_delete": False,
                    "subtype_id": self.env.ref(
                        "bemade_sports_clinic.subtype_patient_injury_internal_update"
                    ).id,
                    "email_layout_xmlid": "mail.mail_notification_light",
                },
            )
        return res

    @api.model
    def _cron_create_injury_verification_tasks(self):
        """Create verification activities for unverified injuries.
        Assign to head therapist(s) of the injury's team, falling back to therapists.
        Runs with sudo to avoid portal ACL constraints from coach-created injuries.
        Deduplicates by checking for existing open 'Verify injury' activities on the same injury/user.
        """
        Activity = self.env['mail.activity'].sudo()
        Injury = self.sudo()
        # Find all unverified injuries
        injuries = Injury.search([('stage', '=', 'unverified')])
        if not injuries:
            return True

        # Use generic To Do activity type
        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)

        for injury in injuries:
            # Determine target team
            team = injury.team_id
            if not team and injury.patient_id.team_ids:
                team = injury.patient_id.team_ids[:1]
            if not team:
                continue

            # Find staff for this team prioritized by head_therapist then therapist
            staff = self.env['sports.team.staff'].sudo().search([
                ('team_id', '=', team.id),
                ('role', 'in', ['head_therapist', 'therapist'])
            ])
            if not staff:
                continue

            # Prefer head therapists
            # Resolve model id once
            model_rec = self.env['ir.model']._get('sports.patient.injury')
            existing = Activity.search([
                ('res_model_id', '=', model_rec.id),
                ('res_id', '=', injury.id),
                ('summary', '=', 'Verify injury'),
                ('active', '=', True),
            ], limit=1)
            if existing:
                continue

            # Choose a single assignee: prefer first head therapist user, else first therapist user
            head_users = staff.filtered(lambda s: s.role == 'head_therapist').mapped('user_ids')[:1]
            therapist_users = staff.filtered(lambda s: s.role == 'therapist').mapped('user_ids')[:1]
            assignee = head_users or therapist_users
            if not assignee:
                continue

            vals = {
                'res_model_id': model_rec.id,
                'res_id': injury.id,
                'user_id': assignee.id,
                'activity_type_id': todo_type.id if todo_type else False,
                'summary': 'Verify injury',
                'note': _("Please verify this injury and set the appropriate status."),
                'date_deadline': fields.Date.context_today(self),
                'automated': True,
            }
            Activity.create(vals)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        # Determine context before creating to avoid mail.followers writes
        # when portal/coach creates. "Treatment professional" covers BOTH
        # internal and portal TPs — the latter must also create injuries
        # in the verified ("active") stage so they don't have to manually
        # bump the stage every time.
        is_treatment_professional = (
            self.env.user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
            or self.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        )
        is_admin = self.env.user.has_group('base.group_system')
        is_internal_user = self.env.user.has_group('base.group_user')
        suppress_notifications = not (is_treatment_professional or is_admin or is_internal_user)

        if suppress_notifications:
            # Disable auto-track, auto-log and auto-subscribe during create
            res = super(PatientInjury, self.with_context(
                mail_notrack=True,
                mail_create_nolog=True,
                mail_create_nosubscribe=True
            )).create(vals_list)
        else:
            res = super().create(vals_list)

        # Task 1241: seed the append-only note history for initially
        # non-empty note fields. Runs under suppression contexts too; only
        # skip_note_history disables it. Task 1404: the strip() guard below
        # is the normalized-empty skip — whitespace-only initial notes seed
        # nothing; stored content stays raw.
        if not self.env.context.get('skip_note_history'):
            history_vals = []
            author_id = self._note_history_author_id()
            now = fields.Datetime.now()
            for record in res:
                for fname, scope in note_history_scope_by_field.items():
                    content = record[fname]
                    if content and content.strip():
                        history_vals.append({
                            'injury_id': record.id,
                            'scope': scope,
                            'content': content,
                            'author_id': author_id,
                            'note_datetime': now,
                        })
            if history_vals:
                self.env['sports.injury.note.history'].sudo().create(history_vals)

        for record in res:
            # Creator role checks (re-use computed flags)
            # is_treatment_professional, is_admin, is_internal_user, suppress_notifications defined above

            # Set initial stage without chatter/autosubscribe for portal/coach creators
            # dashboard_bump: these mid-create writes must not each trigger a
            # dashboard rollup — the single explicit bump below covers the whole
            # new-injury event once (task 1272).
            if is_treatment_professional or is_admin:
                record.with_context(mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True, dashboard_bump=True).write({'stage': 'active'})
            else:
                record.with_context(mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True, dashboard_bump=True).write({'stage': 'unverified'})

            # Automatically assign therapist when creating an injury
            current_user = self.env.user

            # If the injury creator is a treatment professional, assign them
            if current_user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'):
                record.with_context(mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True, dashboard_bump=True).treatment_professional_ids = [(4, current_user.id)]
            # Otherwise, if there's a team_id, find and assign team therapists
            elif record.team_id:
                # sudo: portal users (coach, portal-TP) can read sports.team.staff
                # but cannot traverse staff.user_ids -> res.users.group_ids without it.
                team_staff = self.env['sports.team.staff'].sudo().search([
                    ('team_id', '=', record.team_id.id)
                ])

                # Filter to only staff users who are treatment professionals
                if team_staff:
                    staff_users = team_staff.mapped('user_ids')
                    treatment_prof_group = self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
                    therapist_users = staff_users.filtered(
                        lambda user: treatment_prof_group in user.group_ids
                    )

                    if therapist_users:
                        record.with_context(mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True, dashboard_bump=True).treatment_professional_ids = [(6, 0, therapist_users.ids)]

            if not suppress_notifications:
                # Only internal/therapist flows adjust followers; portal/coach would 403 on mail.followers
                record._manage_treatment_professional_subscriptions()
                # Some flows rely on recomputing followers on patient; keep for staff
                record.patient_id.recompute_followers()

        # Task 1272: a new injury is recent activity for the owning player.
        # Hidden injuries surface to TP only (Law 25).
        if not self.env.context.get('dashboard_bump'):
            for record in res:
                if record.patient_id:
                    roles = {'tp'} if record.hidden_from_coaches else {'coach', 'tp'}
                    record.patient_id._bump_dashboard_activity(roles)

        return res
