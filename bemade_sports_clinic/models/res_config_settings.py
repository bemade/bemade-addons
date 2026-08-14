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
