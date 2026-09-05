from odoo import api, fields, models, _
from odoo.exceptions import AccessError
import logging


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    _logger = logging.getLogger(__name__)

    # Vendor-side (therapist purchase) products
    product_event_coverage_vendor_id = fields.Many2one(
        'product.product', string='Therapist Coverage Product (Vendor PO)',
        config_parameter='bemade_sports_clinic.product_event_coverage_vendor_id')
    product_event_travel_vendor_id = fields.Many2one(
        'product.product', string='Therapist Travel Product (Vendor PO)',
        config_parameter='bemade_sports_clinic.product_event_travel_vendor_id')
    product_event_clinic_vendor_id = fields.Many2one(
        'product.product', string='Clinic Product (Vendor PO)',
        config_parameter='bemade_sports_clinic.product_event_clinic_vendor_id')

    # Team dashboard daily-digest snapshot config (task 1267)
    digest_capture_time = fields.Char(
        string="Digest Capture Time",
        config_parameter="bemade_sports_clinic.digest_capture_time",
        default="00:00",
        help="Team-local clock time (HH:MM) at/after which each team's daily "
             "dashboard-digest snapshot is captured. The hourly cron captures "
             "one snapshot per team per local date.")
    digest_default_timezone = fields.Char(
        string="Digest Default Timezone",
        config_parameter="bemade_sports_clinic.digest_default_timezone",
        help="Fallback timezone used to resolve a team's local capture date when "
             "the team's organization partner has no timezone set (e.g. "
             "'America/Toronto'). Falls back to the company timezone / UTC.")
    # Task 1268: per-user morning-briefing send time (user-local clock)
    digest_morning_send_time = fields.Char(
        string="Morning Briefing Send Time",
        config_parameter="bemade_sports_clinic.digest_morning_send_time",
        default="07:00",
        help="User-local clock time (HH:MM) at/after which each staff member's "
             "daily PHI-free morning briefing is sent. The hourly cron sends one "
             "briefing per user per local date, in the user's own timezone.")
    # Task 1392: system-wide dashboard activity window (hours). The live team
    # dashboard, the portal view and the morning briefing all follow this window;
    # only the daily digest snapshot is pinned to a fixed 24h slice (see
    # sports_team_digest.SNAPSHOT_WINDOW_HOURS) so the history browser never
    # repeats an item across days. Floored at 1h on save (see set_values).
    dashboard_activity_window_hours = fields.Integer(
        string="Dashboard Activity Window (hours)",
        config_parameter="bemade_sports_clinic.dashboard_activity_window_hours",
        default=24,
        help="Recency window (in hours) for the team dashboard, its portal view "
             "and the morning briefing's change counts — e.g. 24 / 48 / 72. The "
             "daily digest snapshot stays a fixed 24h slice regardless. Floored "
             "at 1h; a zero/negative value cannot be saved.")
    # Task 1269: urgent aggregated notifications
    urgent_notify_last_run = fields.Datetime(
        string='Urgent Notifications — Last Run',
        config_parameter='bemade_sports_clinic.urgent_notify_last_run',
        help="Watermark for the 5-minute urgent-notification cron: each run "
             "scans activity since this timestamp, sends the aggregated summary, "
             "then advances it. Rewind it to re-scan an earlier window.")
    legacy_change_emails_enabled = fields.Boolean(
        string='Enable Legacy Per-Change Emails',
        config_parameter='bemade_sports_clinic.legacy_change_emails_enabled',
        help="When off (default), the three legacy per-change follower emails "
             "(play-status update, injury field-edit, internal-note) are "
             "suppressed — urgent activity is delivered by the aggregated "
             "5-minute notification and surfaced on the dashboard/daily digest. "
             "Turn on to restore the old one-email-per-change behaviour.")

    # Task 1244: staleness threshold for the quick-note escalation cron.
    quick_note_stale_days = fields.Integer(
        string="Quick Note Staleness (days)",
        config_parameter="bemade_sports_clinic.quick_note_stale_days",
        default=365,
        help="Age (in days) after which an undismissed quick note raises a "
             "reminder activity for its owner and a summary reminder for the "
             "clinic administrators. Quick notes are never auto-deleted. "
             "A zero/negative value falls back to 365.")

    # Task 1418: retention of unresolved unregistered kiosk sign-ins.
    kiosk_unregistered_retention_days = fields.Integer(
        string="Unregistered Kiosk Sign-ins Retention (days)",
        config_parameter="bemade_sports_clinic.kiosk_unregistered_retention_days",
        default=7,
        help="Days after a clinic ends before its unresolved kiosk sign-ins "
             "(name and date of birth typed by a player who matched no file) "
             "are purged by the daily cron. Rows the therapist linked, created "
             "or removed are not concerned. 0 = never purge.")

    # Task 1433: idle timeout of the kiosk sign-in form. A visitor who walks
    # away mid-form must not leave their typed name on screen: after this many
    # seconds without interaction the kiosk returns to a clean dispatcher.
    kiosk_idle_seconds = fields.Integer(
        string="Kiosk Idle Timeout (seconds)",
        config_parameter="bemade_sports_clinic.kiosk_idle_seconds",
        default=75,
        help="Seconds without interaction before the kiosk sign-in form "
             "abandons back to a clean start screen (and the no-JS fallback "
             "refresh fires). A zero/negative value falls back to 75.")

    # Task 1416: head start of the event-coverage access (task 539) before
    # the coverage starts. 0 = exactly at the start.
    # Not a ``config_parameter`` field on purpose: the generic save drops an
    # Integer 0 (parameter deleted -> default 48 again) and 0 is a valid
    # setting here. get_values / set_values below handle it.
    event_coverage_lead_hours = fields.Integer(
        string="Event Coverage Access Lead (hours)",
        default=48,
        help="Hours before the therapist coverage starts (therapist start or "
             "event start) at which an assigned therapist gets the temporary "
             "team access; the hourly reconcile opens the access on time and "
             "removes it after the coverage ends. 0 = exactly at the start.")

    # Recipient for portal "report material used" notice emails
    material_report_email = fields.Char(
        string='Material Report Recipient',
        config_parameter='bemade_sports_clinic.material_report_email',
        help="Email address pre-filled in the portal Add Timesheet notice inviting "
             "therapists to report personal material used, for client re-invoicing.")

    # Customer-side (organization invoice) products
    product_event_coverage_customer_id = fields.Many2one(
        'product.product', string='Coverage Product (Customer Invoice)',
        config_parameter='bemade_sports_clinic.product_event_coverage_customer_id')
    product_event_travel_customer_id = fields.Many2one(
        'product.product', string='Travel Product (Customer Invoice)',
        config_parameter='bemade_sports_clinic.product_event_travel_customer_id')
    product_event_clinic_customer_id = fields.Many2one(
        'product.product', string='Clinic Product (Customer Invoice)',
        config_parameter='bemade_sports_clinic.product_event_clinic_customer_id')

    @api.model
    def get_values(self):
        res = super().get_values()
        res["event_coverage_lead_hours"] = self.env[
            "sports.event"]._event_coverage_lead_hours()
        return res

    def set_values(self):
        """Floor the dashboard activity window at 1h before persisting.

        A zero/negative window would produce an empty or nonsensical recency
        slice on the live dashboard, portal and briefing; clamp it here so a bad
        value can never be saved (mirrors ``_dashboard_window_hours`` on read).
        Task 1416: the event-coverage lead is floored at 0 and always written
        (0 included).
        """
        for rec in self:
            if (rec.dashboard_activity_window_hours or 0) < 1:
                rec.dashboard_activity_window_hours = 1
            if (rec.event_coverage_lead_hours or 0) < 0:
                rec.event_coverage_lead_hours = 0
        res = super().set_values()
        Event = self.env["sports.event"]
        self.env["ir.config_parameter"].sudo().set_param(
            Event.EVENT_COVERAGE_LEAD_PARAM,
            str(int(self.event_coverage_lead_hours or 0)),
        )
        return res

    def action_recompute_sports_followers_and_groups(self):
        """Admin-only maintenance action to recompute followers and team staff groups.

        - Recomputes followers for all sports patients (and their injuries)
        - Recomputes portal/internal group memberships for all team staff users
        """
        user = self.env.user
        if not (
            user.has_group('base.group_system')
            or user.has_group('bemade_sports_clinic.group_sports_clinic_admin')
        ):
            raise AccessError(_("Only administrators can run this maintenance action."))

        Patient = self.env['sports.patient'].sudo()
        TeamStaff = self.env['sports.team.staff'].sudo()
        Users = self.env['res.users'].sudo()

        # Task 1415: organization staff lines are a source of team staff rows
        # — reconcile them first so the follower / group passes below see the
        # propagated rows (and no orphan ones).
        self.env['sports.organization.staff'].sudo()._cron_sync_organization_staff()
        # Task 1416: same for the timed rows (temporary access grants + event
        # coverage) — idempotent, the hourly job does the same.
        self.env['sports.team.staff'].sudo()._reconcile_timed_rows()

        patients = Patient.search([])
        if patients:
            patients.with_context(
                tracking_disable=True,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_auto_subscribe_no_notify=True,
                mail_notify_force_send=False,
            ).recompute_followers()

        staff = TeamStaff.search([])
        if staff:
            # First, run the bulk staff-based group recomputation
            staff._update_all_portal_groups()

        # Additionally, ensure all users with portal or internal access
        # get their group memberships refreshed based on their staff roles.
        portal_group = self.env.ref('base.group_portal')
        user_group = self.env.ref('base.group_user')
        affected_users = Users.search([
            '|',
            ('group_ids', 'in', portal_group.ids),
            ('group_ids', 'in', user_group.ids),
        ])
        if affected_users:
            empty_staff = TeamStaff.browse()
            for user_rec in affected_users:
                empty_staff._update_all_portal_groups(user_rec)

        # Final safety pass: ensure all coaches/head coaches with portal access
        # have the portal coach group, even if earlier logic missed them.
        portal_coach_group = self.env.ref('bemade_sports_clinic.group_portal_team_coach')
        coach_staff = TeamStaff.search([
            ('role', 'in', ['head_coach', 'coach']),
        ])
        coach_partners = coach_staff.mapped('partner_id')
        coach_users = Users.search([
            ('partner_id', 'in', coach_partners.ids),
            ('group_ids', 'in', portal_group.ids),
        ])
        for user_rec in coach_users:
            if portal_coach_group not in user_rec.group_ids:
                user_rec.sudo().write({'group_ids': [(4, portal_coach_group.id)]})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sports Clinic Maintenance Completed'),
                'message': _(
                    'Followers and team staff group memberships have been recomputed.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_recompute_sports_groups_only(self):
        """Admin-only maintenance action to recompute only team staff groups.

        This skips follower recomputation to make access rights logging easier to inspect.
        """
        user = self.env.user
        if not (
            user.has_group('base.group_system')
            or user.has_group('bemade_sports_clinic.group_sports_clinic_admin')
        ):
            raise AccessError(_("Only administrators can run this maintenance action."))

        TeamStaff = self.env['sports.team.staff'].sudo()
        Users = self.env['res.users'].sudo()

        staff = TeamStaff.search([])
        if staff:
            staff._update_all_portal_groups()

        portal_group = self.env.ref('base.group_portal')
        user_group = self.env.ref('base.group_user')
        affected_users = Users.search([
            '|',
            ('group_ids', 'in', portal_group.ids),
            ('group_ids', 'in', user_group.ids),
        ])
        if affected_users:
            empty_staff = TeamStaff.browse()
            for user_rec in affected_users:
                empty_staff._update_all_portal_groups(user_rec)

        # Final safety pass: ensure all coaches/head coaches with portal access
        # have the portal coach group, even if earlier logic missed them.
        portal_coach_group = self.env.ref('bemade_sports_clinic.group_portal_team_coach')
        coach_staff = TeamStaff.search([
            ('role', 'in', ['head_coach', 'coach']),
        ])
        coach_partners = coach_staff.mapped('partner_id')
        coach_users = Users.search([
            ('partner_id', 'in', coach_partners.ids),
            ('group_ids', 'in', portal_group.ids),
        ])
        for user_rec in coach_users:
            if portal_coach_group not in user_rec.group_ids:
                user_rec.sudo().write({'group_ids': [(4, portal_coach_group.id)]})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sports Clinic Group Maintenance Completed'),
                'message': _(
                    'Team staff group memberships have been recomputed (no follower changes).'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
