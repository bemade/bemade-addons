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
{
    'name': 'Sports Clinic Management',
    'version': '18.0.2.0.0',
    'summary': 'Comprehensive sports medicine clinic management with portal access and activity tracking.',
    'description': """
        Sports Clinic Management System
        =============================

        A comprehensive solution for managing sports medicine clinics, focusing on player health,
        injury tracking, team collaboration, and integrated activity management.

        Key Features:
        ------------

        1. User Roles and Access:
           - Internal clinic staff with full patient record access
           - Treatment professionals with medical record access
           - Portal access for field therapists and team coaches
           - Automated group assignment based on team roles

        2. Player Management:
           - Track player details and contact information with address management
           - Monitor team memberships and playing status
           - Record and track injuries and treatment history
           - Track match and practice availability
           - Emergency contacts management with mobile numbers
           - Canadian address validation (provinces/territories)

        3. Injury Tracking:
           - Comprehensive injury recording and documentation
           - Treatment professional assignment and parental consent tracking
           - Progress tracking and resolution monitoring
           - Internal and external notes for different audiences
           - Document attachment support with portal access
           - Injury status workflow (Unverified → Active → Resolved)

        4. Team Management:
           - Organize players into teams with staff assignments
           - Assign coaching and medical staff with automatic portal access
           - Team-specific player status tracking
           - Player removal workflow with approval process
           - Treatment notes management across team members

        5. Activity Management (NEW):
           - Integrated mail.activity system for task management
           - Portal access to activities for treatment professionals
           - Activity creation, completion, and reassignment
           - Team-based activity filtering and access control
           - Activity counts and navigation throughout portal
           - Activity detail views with attachment support

        6. Portal Access:
           - Coaches can view their teams and player status
           - Field therapists can access and update medical records
           - Injury reporting directly through the portal
           - Comprehensive activity management interface
           - Player removal requests with reason tracking
           - Emergency contacts and address management
           - Document upload and download capabilities
           - Messages and attachments portal access

        7. Security and Privacy:
           - Layered security architecture (ACL + Record Rules + Controller filtering)
           - Team-based access control throughout the system
           - Field-level security for sensitive information
           - Audit trails for all changes
           - GDPR and Quebec Law 25 compliance features
           - Configurable data retention policies
           - RPC security protection with buddy method pattern
           
        8. Data Protection:
           - Scheduled data anonymization
           - Configurable retention periods
           - Audit logging of all data handling
           - Manual anonymization wizard

        9. Localization:
           - Full French Canadian (fr_CA) translation support
           - Canadian-specific address and province handling
           - Localized date and number formatting

        10. Integration Features:
            - Mail system integration for notifications
            - Project task integration for event management
            - Task-to-event conversion wizard
            - Comprehensive demo data for testing

        This module provides a complete sports medicine clinic management solution with
        robust portal access, activity tracking, and team collaboration features while
        maintaining strict security and data privacy controls.
    """,
    "category": "Services/Medical",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "mail",  # Required for mail.activity functionality
        "portal", 
        "contacts",
        "phone_validation",  # For phone number formatting in patient contacts
        "project",  # Required for project.task (Events) functionality
    ],
    "external_dependencies": {
        "python": [
            "openupgradelib",
            "pytz",  # For timezone handling in injury tracking
        ],
    },
    "data": [
        "security/sports_clinic_groups.xml",
        "security/sports_clinic_portal_groups.xml",
        "security/ir.model.access.csv",
        "security/sports_clinic_rules.xml",
        "security/sports_clinic_portal_rules.xml",
        "security/mail_activity_portal_rules.xml",
        "security/project_task_portal_rules.xml",
        "security/sports_event_rules.xml",
        "security/partner_access.xml",
        "data/sports_clinic_data.xml",
        "data/admin_access_data.xml",
        # "data/project_portal_demo_data.xml",  # Temporarily disabled for clean upgrade
        "data/cron_actions.xml",
        "views/sports_team_views.xml",
        "views/sports_clinic_menus.xml",
        "views/sports_patient_injury_views.xml",
        "views/sports_patient_views.xml",
        "views/sports_clinic_portal_views.xml",
        "views/sports_patient_injury_portal.xml",
        "views/player_management_portal_templates.xml",
        "views/injury_management_portal_templates.xml",
        "views/task_management_portal_templates.xml",
        "views/events_portal_templates.xml",
        "views/project_task_views.xml",
        "views/project_task_security_test_views.xml",
        "views/sports_event_views.xml",
        "views/portal_activity_detail_template.xml",
        "views/portal_messages_template.xml",
        "views/portal_attachments_template.xml",
        "views/portal_event_detail_template.xml",
        "views/portal_event_edit_template.xml",
        "views/treatment_note_views.xml",
        "views/res_partner_views.xml",
        "views/res_users_views.xml",
        "views/task_to_event_wizard_views.xml",
    ],
    "demo": ["data/demo/sports_clinic_demo_data.xml"],
    "installable": True,
    "auto_install": False,
    "application": True,
}
