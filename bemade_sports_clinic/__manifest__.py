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
    'version': '18.0.1.6.2',
    'summary': 'Manage the patients of a sports medicine clinic.',
    'description': """
        Sports Clinic Management System
        =============================

        A comprehensive solution for managing sports medicine clinics, focusing on player health,
        injury tracking, and team collaboration.

        Key Features:
        ------------

        1. User Roles and Access:
           - Internal clinic staff with full patient record access
           - Treatment professionals with medical record access
           - Portal access for field therapists and team coaches

        2. Player Management:
           - Track player details and contact information
           - Monitor team memberships and playing status
           - Record and track injuries and treatment history
           - Track match and practice availability

        3. Injury Tracking:
           - Comprehensive injury recording and documentation
           - Treatment professional assignment
           - Progress tracking and resolution monitoring
           - Internal and external notes for different audiences

        4. Team Management:
           - Organize players into teams
           - Assign coaching and medical staff
           - Team-specific player status tracking

        5. Portal Access:
           - Coaches can view their teams and player status
           - Field therapists can access and update medical records
           - Injury reporting directly through the portal

        6. Security and Privacy:
           - Granular permission system
           - Field-level security for sensitive information
           - Audit trails for all changes

        This module is designed to facilitate communication between medical professionals,
        coaching staff, and administrative personnel while maintaining appropriate access
        controls and data privacy.
    """,
    "category": "Services/Medical",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["portal", "contacts"],
    "external_dependencies": {
        "python": [
            "openupgradelib",
        ],
    },
    "data": [
        "security/sports_clinic_groups.xml",
        "security/sports_clinic_portal_groups.xml",
        "security/ir.model.access.csv",
        "security/sports_clinic_rules.xml",
        "security/sports_clinic_portal_rules.xml",
        "data/sports_clinic_data.xml",
        "data/admin_access_data.xml",
        "views/sports_team_views.xml",
        "views/sports_clinic_menus.xml",
        "views/sports_patient_injury_views.xml",
        "views/sports_patient_views.xml",
        "views/sports_clinic_portal_views.xml",
        "views/sports_patient_injury_portal.xml",
        "views/res_partner_views.xml",
        "views/res_users_views.xml",
    ],
    "demo": ["data/demo/sports_clinic_demo_data.xml"],
    "installable": True,
    "auto_install": False,
    "application": True,
}
